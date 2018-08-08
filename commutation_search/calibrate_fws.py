import sys
import asyncio
import logging

import aerotech

logger = logging.getLogger(__name__)


async def _run_with_timeout(coro, timeout):
    fut = asyncio.ensure_future(coro)
    await asyncio.wait([fut], timeout=timeout)
    if not fut.done():
        raise asyncio.TimeoutError()
    return fut.result()


async def make_connection(host, comm_port):
    logger.debug('Connecting to %s:%d', host, comm_port)
    comm = aerotech.EnsembleDoCommand(host, comm_port)
    while comm._reader is None:
        try:
            await _run_with_timeout(comm._open_connection(), timeout=2.0)
        except ConnectionRefusedError:
            logger.debug('Connection refused; retrying')
        except asyncio.TimeoutError:
            logger.debug('Connection timed out; retrying')

    logger.debug('Connected')

    try:
        await _run_with_timeout(comm.check_program_status(), timeout=2.0)
    except asyncio.TimeoutError:
        logger.debug('Timeout after initial connection; retrying')
        await asyncio.sleep(1.0)
        return await make_connection(host, comm_port)
    except ConnectionResetError:
        logger.debug('Connection reset after attempt; retrying connection')
        await asyncio.sleep(1.0)
        return await make_connection(host, comm_port)

    return comm


async def check_commutation_offset(host, comm_port, scope_port,
                                   commutation_offset, *,
                                   use_scope_program=False, axis_name='X'):
    comm = await make_connection(host, comm_port)
    axis_status = await comm.get_axis_status(axis_name)
    if aerotech.AxisStatus.InPosition in axis_status:
        await comm.move_and_wait({axis_name: 2.2}, speed=5, absolute=True)

    await comm.write_read('DISABLE {}'.format(axis_name))
    await comm.write_read('SETPARM {}, CommutationOffset, {}'
                          ''.format(axis_name, commutation_offset))

    try:
        await comm.commit_parameters()
        await asyncio.sleep(1.0)
        await comm.reset()
        await asyncio.sleep(9.0)
    except aerotech.TimeoutResponseException:
        ...

    comm = await make_connection(host, comm_port)
    await asyncio.sleep(2.0)

    while True:
        fault_status = await comm.get_axis_fault_status(axis_name)
        if int(fault_status) == 0:
            break
        else:
            logger.debug('Axis in fault condition: %s', fault_status)
            await asyncio.sleep(0.5)

    in_position = await comm.wait_axis_status(
        axis_name, flags=aerotech.AxisStatus.InPosition, poll_period=0.1,
        check_enabled=True)

    if not in_position:
        ...
        # recovery script made the axis move to 0 and disable

    await asyncio.sleep(2.0)

    data_points = 2000
    await comm.move_and_wait({axis_name: 2.2}, speed=5, absolute=True,
                             poll_period=0.1)
    await comm.scope_start(data_points=data_points, period_ms=10)
    await comm.move_and_wait({axis_name: 42.}, speed=5, absolute=True,
                             poll_period=0.1)
    await comm.move_and_wait({axis_name: 2.2}, speed=5, absolute=True,
                             poll_period=0.1)
    await asyncio.sleep(0.15)
    await comm.scope_stop()
    await comm.scope_wait()

    scopereader = aerotech.ScopeDataReader(comm, host=host,
                                           port=scope_port)
    dataset = await _run_with_timeout(scopereader.read_data(),
                                      timeout=10.0)
    return dataset


async def calibrate_fws(host, comm_port, scope_port, *, acquire=False,
                        low=326, high=360, step=2, use_scope_program=False,
                        axis_name='X'):
    data = {}

    offsets = list(range(low, high, step))
    while len(offsets):
        commutation_offset = offsets[0]
        logger.info('* Checking offset %d', commutation_offset)
        try:
            while True:
                try:
                    dataset = await check_commutation_offset(
                        host=host, comm_port=comm_port, scope_port=scope_port,
                        commutation_offset=commutation_offset,
                        use_scope_program=use_scope_program, axis_name=axis_name)
                except KeyboardInterrupt:
                    raise
                except Exception as ex:
                    logger.exception('Check offset failed')
                    await asyncio.sleep(1.0)
                    continue
                else:
                    break

            data[commutation_offset] = dataset
            data_point, pos_cmd, pos_fbk, cur_cmd, cur_fbk = dataset

            with open('results-{}-{}.txt'.format(low, high), 'wt') as f:
                print(data, file=f)
        except KeyboardInterrupt:
            response = input('Continue? [Y/n]')
            if response.strip().lower() not in ('', 'y'):
                return
        else:
            logger.info('Successfully completed offset angle: %d',
                        commutation_offset)
            offsets.pop(0)

    logger.info('Successfully completed all requested offsets')
    logger.info('Done')


def _parse_args():
    import argparse

    parser = argparse.ArgumentParser(
        description='Calibrate FWS commutation offset'
    )
    parser.add_argument('host', type=str,
                        help='Controller hostname/IP')
    parser.add_argument('start', type=int,
                        help='Starting angle')
    parser.add_argument('stop', type=int,
                        help='Last angle to attempt')
    parser.add_argument('step', type=int,
                        help='Increment between angles')
    parser.add_argument('--axis', default='@0', type=str,
                        help='Axis name (X, Y, @0, @1, etc.); default @0')
    parser.add_argument('--comm', default=8000, type=int,
                        help='Comm port (usually socket 2)')
    parser.add_argument('--scope', default=8001, type=int,
                        help='Scope port (usually socket 3)')
    return parser.parse_args(sys.argv[1:])


if __name__ == '__main__':
    info = _parse_args()
    logging.getLogger('aerotech').setLevel(logging.DEBUG)
    logger.setLevel(logging.DEBUG)

    logging.basicConfig(
        format='%(asctime)s.%(msecs)03d %(levelname)-8s %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S')

    future = calibrate_fws(info.host, comm_port=info.comm,
                           scope_port=info.scope, low=info.start,
                           high=info.stop, step=info.step, axis_name=info.axis)

    loop = asyncio.get_event_loop()
    loop.run_until_complete(future)
    loop.close()

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
        return await make_connection(host, comm_port)
    except ConnectionResetError:
        logger.debug('Connection reset after attempt; retrying connection')
        return await make_connection(host, comm_port)

    return comm


async def calibrate_fws(host, comm_port, scope_port, *, acquire=False,
                        low=320, high=330):
    comm = await make_connection(host, comm_port)

    data = {}
    for commutation_offset in range(low, high):
        axis_status = await comm.get_axis_status('X')
        if aerotech.AxisStatus.InPosition in axis_status:
            await comm.move_and_wait(dict(X=2.2), speed=5, absolute=True)

        await comm.write_read('DISABLE X')
        await comm.write_read('SETPARM X, CommutationOffset, {}'
                              ''.format(commutation_offset))

        try:
            await comm.commit_parameters()
        except aerotech.TimeoutResponseException:
            ...

        await comm.reset()

        await asyncio.sleep(20.0)

        comm = await make_connection(host, comm_port)
        await asyncio.sleep(5.0)

        while True:
            fault_status = await comm.get_axis_fault_status('X')
            if int(fault_status) == 0:
                break
            else:
                logger.debug('Axis in fault condition: %s', fault_status)
                await asyncio.sleep(0.5)

        await comm.wait_axis_status('X', aerotech.AxisStatus.InPosition)
        await asyncio.sleep(2.0)

        data_points = 2000
        await comm.move_and_wait(dict(X=2.2), speed=5, absolute=True)
        await comm.scope_start(data_points=data_points, period_ms=10)
        await comm.move_and_wait(dict(X=42), speed=5, absolute=True)
        await comm.move_and_wait(dict(X=2.2), speed=5, absolute=True)
        await asyncio.sleep(0.15)
        await comm.scope_stop()
        await comm.scope_wait()

        while True:
            scopereader = aerotech.ScopeDataReader(comm, host=host,
                                                   port=scope_port)

            # TODO scope reader is having trouble with larger datasets...
            try:
                dataset = await _run_with_timeout(scopereader.read_data(),
                                                  timeout=10.0)
            except Exception:
                logger.exception('Failed to read data set')
                await asyncio.sleep(0.5)
                continue
            else:
                break

        data[commutation_offset] = dataset
        data_point, pos_cmd, pos_fbk, cur_cmd, cur_fbk = dataset

        with open('results-{}-{}.txt'.format(low, high), 'wt') as f:
            print(data, file=f)


if __name__ == '__main__':
    try:
        host = sys.argv[1]
    except IndexError:
        host = 'moc-b34-mc07.slac.stanford.edu'
        # host = 'moc-b34-mc08.slac.stanford.edu'

    logging.getLogger('aerotech').setLevel(logging.DEBUG)
    logger.setLevel(logging.DEBUG)

    logging.basicConfig(
        format='%(asctime)s.%(msecs)03d %(levelname)-8s %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S')

    loop = asyncio.get_event_loop()
    loop.run_until_complete(calibrate_fws(host, comm_port=8000,
                                          scope_port=8001))
    loop.close()

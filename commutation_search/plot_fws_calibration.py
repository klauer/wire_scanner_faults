import sys
import ast

import numpy as np
import matplotlib
matplotlib.use('Qt5Agg')  # noqa
import matplotlib.pyplot as plt


def plot(data, skip):
    info = dict(offset=[], average=[], positions=[], current=[])

    for offset, (idx, pos_cmd, pos_fbk, cur_cmd, cur_fbk) in data.items():
        if offset < 180:
            offset += 360

        pos_fbk = np.asarray(pos_fbk) / 1000.
        valid_idx = pos_fbk > 2.0
        cur_fbk = np.asarray(cur_fbk)[valid_idx]
        pos_fbk = pos_fbk[valid_idx]
        max_pos = np.max(pos_fbk)

        avg = np.average(cur_fbk[(pos_fbk >= 5) & (pos_fbk <= 41)])

        if max_pos < 41.1 and skip:
            print('Discarding offset {} (max pos = {})'
                  ''.format(offset, max_pos))
            pos_fbk = []
            cur_fbk = []
        else:
            print('Including offset {} (max pos = {})'
                  ''.format(offset, max_pos))

        info['offset'].append(offset)
        info['average'].append(avg)
        info['positions'].append(pos_fbk)
        info['current'].append(cur_fbk)

    min_idx = np.argmin(info['average'])
    min_offset = info['offset'][min_idx]
    min_avg = info['average'][min_idx]

    marker_positions = []

    for offset, pos_fbk, cur_fbk, avg in zip(info['offset'], info['positions'],
                                             info['current'], info['average']):
        if not len(pos_fbk):
            continue

        marker = ('x-' if offset == min_offset
                  else '--')

        marker_positions.append((offset, avg))
        alpha = (1.0 - (avg - min_avg) / avg) ** 3
        plt.plot(pos_fbk, cur_fbk, marker,
                 label='{} deg; {:.3f}A'.format(offset, avg),
                 markersize=1.0, linewidth=1.0, alpha=alpha)

    plt.title('Commutation angle search')
    plt.ylabel('Current at 160VDC [A]')
    plt.xlabel('Position [mm]')

    plt.subplots_adjust(top=0.88, bottom=0.11, left=0.175, right=0.9,
                        hspace=0.2, wspace=0.2)

    leg = plt.figlegend(loc=(0, 0.1))
    leg.draggable()
    # plt.show()

    plt.figure()
    plt.title('Commutation angle search')
    plt.xlabel('Commutation offset [deg]')
    plt.ylabel('Average current over scan [A]')
    plt.plot('offset', 'average', data=info)
    for offset, avg in marker_positions:
        plt.plot([offset], [avg], 'x')
    plt.show()
    return info


def _parse_args():
    import argparse

    parser = argparse.ArgumentParser(
        description='Calibrate FWS commutation offset'
    )
    parser.add_argument(
        'filenames', type=str, nargs='+',
        help='List of dataset filenames (e.g., results-300-330.txt)')
    parser.add_argument(
        '--no-skip', action='store_true', default=False,
        help='Include results which do not allow for the full travel range')
    return parser.parse_args(sys.argv[1:])


if __name__ == '__main__':
    args = _parse_args()
    fns = args.filenames
    skip = not args.no_skip

    full_data = {}
    for fn in fns:
        with open(fn, 'rt') as f:
            data = f.read().strip()

        full_data.update(ast.literal_eval(data))

    # plt.ion()
    info = plot(full_data, skip=skip)

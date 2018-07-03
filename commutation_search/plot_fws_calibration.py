import sys
import asyncio
import ast

import numpy as np
import logging
import matplotlib
matplotlib.use('Qt5Agg')  # noqa
import matplotlib.pyplot as plt


def plot(data):
    info = dict(offset=[], average=[], positions=[], current=[])

    for offset, (data_point, pos_cmd, pos_fbk, cur_cmd, cur_fbk) in data.items():
        if offset < 10:
            offset += 360

        pos_fbk = np.asarray(pos_fbk[30:-50]) / 1000.
        cur_fbk = np.asarray(cur_fbk[30:-50])
        avg = np.average(cur_fbk)

        info['offset'].append(offset)
        info['average'].append(avg)
        info['positions'].append(pos_fbk)
        info['current'].append(cur_fbk)

    min_avg = np.argmin(info['average'])
    min_offset = info['offset'][min_avg]
    min_avg = info['average'][min_avg]

    for offset, pos_fbk, cur_fbk in zip(info['offset'], info['positions'],
                                        info['current']):
        marker = ('x-' if offset == min_offset
                  else '--')
        print(offset, marker)

        avg = np.average(cur_fbk)
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
    plt.show()


if __name__ == '__main__':
    try:
        fns = sys.argv[1:]
    except IndexError:
        print('Usage: {} results_filename.txt'.format(sys.argv[0]))
        sys.exit(1)

    full_data = {}
    for fn in fns:
        with open(fn, 'rt') as f:
            data = f.read().strip()

        full_data.update(ast.literal_eval(data))

    plot(full_data)

from sys import argv

from _4chan import _4chan


if __name__ == '__main__':
    if len(argv) < 2:
        raise ValueError('not enough parameters')

    _4c = _4chan()

    for board in argv[1:]:
        _4c.refresh_board_cache(board)

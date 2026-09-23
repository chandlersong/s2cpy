from typing import List, Tuple

from s2cpy.model.option import Option


def sort_options_by_strike(options: List[Option], price: float) -> Tuple[List[Option], int]:
    """
    1. 把option按照strike排序，有小到大。然后返回
    2. 找到最接近的price的option的indx
    :param options: 期权
    :param price: 价格
    :return: 排序好的option，和strike最接近price的的index
    """
    if not options:
        return [], -1

    sorted_options = sorted(options, key=lambda option: option.strike)
    closest_index = min(
        range(len(sorted_options)),
        key=lambda idx: (
            abs(sorted_options[idx].strike - price),
            sorted_options[idx].strike,
        ),
    )
    return sorted_options, closest_index

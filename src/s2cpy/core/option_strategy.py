from typing import List

from s2cpy.model.option import CMOption, OptionList, Leg


def generate_butterflies(
        option_list: OptionList,
        max_distance: float = None,  # 中心距离现价超过这个值就不要（None表示不限制）
        equal_wing: bool = True
) -> List[List[Leg]]:
    """
    生成靠近当前价格的蝶式（Call Butterfly + Put Butterfly）
    返回：[[leg1, leg2, leg3], ...]
    """
    calls = option_list.call
    puts = option_list.put
    underlying_price = option_list.underlying_price
    result = []
    call_least_otm_index = option_list.call_least_otm_index
    call_biggest_itm_index = call_least_otm_index - 1

    # Call Butterfly
    for i in range(len(puts)):
        for j in range(i + 1, len(puts)):
            for k in range(j + 1, len(puts)):
                k1, k2, k3 = calls[i], calls[j], calls[k]

                if equal_wing and abs((k2.strike - k1.strike) - (k3.strike - k2.strike)) > 1e-6:
                    continue

                # 只保留中心靠近现价的
                if max_distance is not None and abs(k2.strike - underlying_price) > max_distance:
                    continue

                legs = [
                    Leg(k1, 1),
                    Leg(k2, -2),
                    Leg(k3, 1),
                ]
                result.append(legs)

    # Put Butterfly
    # for i in range(len(puts)):
    #     for j in range(i + 1, len(puts)):
    #         for k in range(j + 1, len(puts)):
    #             k1, k2, k3 = puts[i].strike, puts[j].strike, puts[k].strike
    #
    #             if equal_wing and abs((k2 - k1) - (k3 - k2)) > 1e-6:
    #                 continue
    #
    #             if max_distance is not None and abs(k2 - spot) > max_distance:
    #                 continue
    #
    #             legs = [
    #                 CMOption(k1, puts[i].premium, 1, puts[i].multiplier),
    #                 CMOption(k2, puts[j].premium, -2, puts[j].multiplier),
    #                 CMOption(k3, puts[k].premium, 1, puts[k].multiplier),
    #             ]
    #             result.append(legs)

    # 按中心距离现价从近到远排序
    result.sort(key=lambda legs: abs(legs[1].option.strike - underlying_price))
    return result

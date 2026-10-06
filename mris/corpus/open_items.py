VERIFIED_STATUS = "VERIFIED_AGAINST_GAZETTE"


def open_items(instruments):
    return [i for i in instruments if i.get("verification_status") != VERIFIED_STATUS]

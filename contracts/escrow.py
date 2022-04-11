from pyteal import *


def approval_program():
    print("Approval Program")
    return Approve()


def clear_state_program():
    print("Clear Program")
    return Approve()


if __name__ == "__main__":
    with open("compiled/escrow_approval.teal", "w") as f:
        compiled = compileTeal(approval_program(), mode=Mode.Application, version=5)
        f.write(compiled)

    with open("compiled/escrow_clear_state.teal", "w") as f:
        compiled = compileTeal(clear_state_program(), mode=Mode.Application, version=5)
        f.write(compiled)

import sys
from pathlib import Path

sys.path.append(Path(__file__).parent.parent.as_posix())


import os
os.environ["STATESGROUP_LOGGING"] = "1"
from fsm.state_group import *


class OtherState(State):
    state_type = StateType.CUSTOM

    def handler(self) -> bool:
        print("Some")

        self.group.set_state(self.group.states[-1])
        return True


class OtherOtherState(State):
    state_type = StateType.CUSTOM

    def handler(self) -> bool:
        self.group.set_state(TestStateGroup.StateTwo)

        return True


class TestStateGroup(StatesGroup):
    MARKDOWN = True
    LOGGING = True

    class StateOne(State):

        def handler(self) -> bool:
            print(10)
            return True

    # OtherState = OtherState()

    OtherOtherState = OtherOtherState()

    class IntState(State):
        state_type = StateType.INTERMEDIATE

        def handler(self) -> bool:
            self.group.result = "IntSome"
            return True

    class StateTwo(State):

        def handler(self) -> bool:
            print(20)
            print(self.markdown_section.content)
            self.group.result = "Antonio"
            self.markdown_section.content = "LOL"
            self.markdown_section.file.save()
            return True


if __name__ == "__main__":
    print("Test1")
    for state in TestStateGroup():
        print(state)

    print("Test2")

    send_generator = TestStateGroup().send_generator

    while True:
        try:
            a = send_generator.send(None)
            print(a)
        except Exception as ex:
            print(ex)
            break

    print("Test3")

    print(TestStateGroup().forward_run(OtherOtherState))

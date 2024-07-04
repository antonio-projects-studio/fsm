from __future__ import annotations

__all__ = [
    "State",
    "StateType",
    "SpecialState",
    "default_state",
    "any_state",
    "StatesGroupMeta",
    "StatesGroup",
]

import re
import inspect
from functools import wraps
from typing import Any, Iterator, Callable, overload
from dataclasses import dataclass
from terminal_app.logging import LoggingMeta, RootLogging
from markdown_reader import MarkdownFile, MarkdownSection
from abc import abstractmethod
from enum import StrEnum, auto
from pathlib import Path


def coroutine(func):
    @wraps(func)
    def wrapper_coroutine(*args, **kwargs):
        f = func(*args, **kwargs)
        next(f)
        return f

    return wrapper_coroutine


class StateType(StrEnum):
    DEFAULT = auto()
    CUSTOM = auto()
    INTERMEDIATE = auto()
    FINISH = auto()


class SpecialState(StrEnum):
    ANY = auto()
    NONE = auto()


@dataclass
class PreState:
    name: str
    state_cls: type[State]


class State:
    _group_cls: type[StatesGroup]
    _state: str
    group: StatesGroup
    state_type: StateType = StateType.DEFAULT
    next_state: State | None
    previous_state: State | None
    description: str
    markdown_section: MarkdownSection

    @overload
    def __init__(self) -> None:
        pass

    @overload
    def __init__(self, any_no: SpecialState, /) -> None:
        pass

    @overload
    def __init__(self, owner_instance: StatesGroup, name: str, /) -> None:
        pass

    def __init__(self, *args) -> None:
        assert len(args) in [0, 1, 2]

        if len(args) == 0:
            return

        if len(args) == 1:
            assert args[0] in SpecialState
            self._state = args[0]
            return

        owner_instance, name = args[0], args[1]

        self.__set_name__(owner_instance, name)

    @abstractmethod
    def handler(self) -> bool:
        pass

    @property
    def state(self) -> str:
        if self._state in SpecialState:
            return self._state

        group = self._group_cls.__full_group_name__

        return f"{group}:{self._state}"

    def set_parent(self, group: type[StatesGroup]) -> None:
        if not issubclass(group, StatesGroup):
            raise ValueError("Group must be subclass of StatesGroup")
        self._group_cls = group

    def __set_name__(self, owner: type[StatesGroup] | StatesGroup, name: str) -> None:
        # any_no state can't be in StateGroup
        assert getattr(self, "_state", None) is None

        self._state = name
        if inspect.isclass(owner):
            self.set_parent(owner)
        else:
            self.set_parent(owner.__class__)

        if getattr(self, "state_message", None) is None:
            self.description = self._state

    def __str__(self) -> str:
        return self._state

    def __repr__(self) -> str:
        return f"<State '{self.state or ''}'>"

    def __eq__(self, other: Any) -> bool:
        if inspect.isclass(other):
            return self.__class__ == other
        if isinstance(other, self.__class__):
            return self.state == other.state
        if isinstance(other, str):
            return self.state == other
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.state)


# TODO parent instance class
class StatesGroupMeta(LoggingMeta):
    __parent__: type[StatesGroup] | None
    __children__: tuple[type[StatesGroup], ...]
    __pre_states__: tuple[PreState | State, ...]
    __cls_path__: Path

    def __new__(
        mcs,
        class_name: str,
        bases: tuple[type, ...],
        namespace: dict[str, Any],
        **kwargs,
    ):
        cls = super(StatesGroupMeta, mcs).__new__(mcs, class_name, bases, namespace)

        pre_states = []
        children = []

        for name, arg in namespace.items():
            if inspect.isclass(arg) and issubclass(arg, State):
                pre_states.append(PreState(name=name, state_cls=arg))
            elif isinstance(arg, State):
                pre_states.append(arg)
            elif inspect.isclass(arg) and issubclass(arg, StatesGroup):
                children.append(arg)
                arg.__parent__ = cls

        cls.__parent__ = None
        cls.__children__ = tuple(children)
        cls.__pre_states__ = tuple(pre_states)
        cls.__cls_path__ = Path(inspect.getfile(cls))

        return cls

    @property
    def __full_group_name__(cls) -> str:
        if cls.__parent__:
            return ".".join((cls.__parent__.__full_group_name__, cls.__name__))
        return cls.__name__

    @property
    def __all_children__(cls) -> tuple[type[StatesGroup], ...]:
        result = cls.__children__
        for child in cls.__children__:
            result += child.__children__
        return result

    def __str__(self) -> str:
        return f"<StatesGroup '{self.__full_group_name__}'>"


def state_decorator(current_state: State) -> Callable:

    def decorator(func: Callable[..., bool]):

        @wraps(func)
        def wrapper() -> Any:

            result = func()

            if result == False:
                return

            if (
                current_state.state_type == StateType.FINISH
                or current_state.state_type == StateType.INTERMEDIATE
            ):
                current_state.group.set_state(None)
            else:
                current_state.group.set_state(current_state.next_state)

        return wrapper

    return decorator


class StatesGroup(RootLogging, metaclass=StatesGroupMeta):
    result: Any = None
    package: Any = None
    current_state: State | None = None
    states: tuple[State, ...]
    state_names: tuple[str, ...]
    last_state: State
    markdown_file: MarkdownFile

    MARKDOWN: bool = False

    def __init__(self) -> None:
        self.build_states()
        if self.MARKDOWN:
            self.build_markdown()
        self.decorate_handlers()
        self.current_state = self.set_start_state()

    @classmethod
    def get_root(cls) -> type[StatesGroup]:
        if cls.__parent__ is None:
            return cls
        return cls.__parent__.get_root()

    def root_log_message(
        self, previous_state: State | None, new_state: State | None
    ) -> None:
        self.root_logger.info(f"{previous_state} -> {new_state}")

    def build_states(self) -> None:
        states: list[State] = []
        for state in self.__pre_states__:
            if isinstance(state, PreState):
                state = state.state_cls(self, state.name)
            state.group = self
            states.append(state)

        self.states = tuple(states)
        self.state_names = tuple(state.state for state in states)
        self.current_state = self.states[0]

        for ind, state in enumerate(self.states):
            if ind > 0:
                state.previous_state = self.states[ind - 1]

            if ind == 0:
                state.previous_state = None

            if ind == len(self.states) - 1:
                state.next_state = None
                break

            state.next_state = self.states[ind + 1]

    def build_markdown(self) -> None:
        markdown_path = self.__cls_path__.parent / (self.__cls_path__.stem + ".md")

        if not markdown_path.exists():
            with open(markdown_path, "w") as f:
                md_header = f"# {self.__class__.__name__}\n\n"
                md_states = "\n\n".join([f"## {str(state)}" for state in self.states])
                f.write(md_header + md_states)

        else:
            self.markdown_file = MarkdownFile(markdown_path)
            for state in self.states:
                state.markdown_section = self.markdown_file.header.children[
                    str(state._state)
                ]

    def decorate_handlers(self) -> None:
        for state in self.states:
            if not state.state_type == StateType.CUSTOM:
                state.handler = state_decorator(state)(state.handler)

    def set_start_state(self) -> State:
        return self.states[0]

    def global_transition(self) -> State | type[State] | None:
        return None

    def exit_state(self, previous_state: State) -> None:
        pass

    def enter_state(self, new_state: State) -> None:
        pass

    def set_state(self, new_state: State | type[State] | None) -> None:

        previous_state = self.current_state

        if self.current_state is not None:
            self.last_state = self.current_state

        if previous_state:
            self.exit_state(previous_state)

        if inspect.isclass(new_state):
            ind = [state.__class__ for state in self.states].index(new_state)
            new_state = self.states[ind]

        if new_state:
            self.enter_state(new_state)

        self.current_state = new_state

        if getattr(self, "root_logger", None) is not None:
            self.root_log_message(previous_state, self.current_state)

    def state_logic(self, state: State) -> None:
        state.handler()

    def forward_run(self, state: State | type[State] | None = None) -> Any:
        if state is not None:
            if isinstance(state, State):
                assert state in self.states
                self.current_state = state
            if inspect.isclass(state):
                ind = [state.__class__ for state in self.states].index(state)
                self.current_state = self.states[ind]

        while self.current_state:
            self.state_logic(self.current_state)

            new_state = self.global_transition()

            if new_state is not None:
                self.set_state(new_state)

        return self.result

    def __iter__(self) -> Iterator:
        return self

    def __next__(self) -> Any | type[StopIteration]:
        if getattr(self, "last_state", None) is None:
            return self.forward_run()

        if (
            self.last_state.state_type == StateType.FINISH
            or self.last_state.next_state is None
        ):
            raise StopIteration

        return self.forward_run(self.last_state.next_state)

    @property
    @coroutine
    def send_generator(self):
        fsm = iter(self)

        self.package = yield
        while True:
            self.package = yield next(fsm)

    def __contains__(self, item: Any) -> bool:
        if isinstance(item, str):
            return item in self.state_names
        if isinstance(item, State):
            return item in self.states
        if isinstance(item, StatesGroupMeta):
            return item in self.__children__
        return False

    def __str__(self) -> str:
        return f"StatesGroup {type(self).__full_group_name__}"


default_state = State(SpecialState.NONE)
any_state = State(SpecialState.ANY)

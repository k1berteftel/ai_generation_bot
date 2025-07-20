from aiogram.fsm.state import State, StatesGroup


class UpdateLinkOp(StatesGroup):
    new_link = State()


class OpState(StatesGroup):
    id = State()
    link = State()


class NameUrl(StatesGroup):
    name = State()


class ApiKeyStates(StatesGroup):
    waiting_for_key = State()


class StartMessage(StatesGroup):
    mes = State()


class SetStartMessageDelay(StatesGroup):
    delay = State()
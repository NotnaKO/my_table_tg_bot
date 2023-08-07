from abc import ABC, abstractmethod
from typing import List

import gspread

gc = gspread.service_account(filename='my-python-project-394918-c67628393454.json')


class BaseChecker(ABC):
    """Base class of table checkers"""
    reference: str
    worksheet_index: int
    answer: str

    def __init__(self, ref: str, worksheet: int):
        self.reference = ref
        self.worksheet_index = worksheet
        self.data = []
        self.answer = ''

    def update(self) -> None:
        sh = gc.open_by_url(self.reference)
        new_data = self.get_data(sh.get_worksheet(self.worksheet_index))
        self.get_news(new_data)
        self.data = new_data

    @abstractmethod
    def get_data(self, wh: gspread.Worksheet):
        raise NotImplementedError

    @abstractmethod
    def get_news(self, new_data: List) -> None:
        raise NotImplementedError


class CellChecker(BaseChecker):
    target: str

    def __init__(self, ref: str, worksheet: int, target: str):
        super().__init__(ref, worksheet)
        self.target = target
        self.data = None
        self.update()

    def get_data(self, wh: gspread.Worksheet):
        return wh.acell(self.target).value

    def get_news(self, new_data: List) -> None:
        self.answer = ''
        if self.data != new_data:
            self.answer = f"Ячейка {self.target} изменена с {self.data} на {new_data}\n"


class RowChecker(BaseChecker):
    row_index: int

    def __init__(self, ref: str, worksheet: int, row_index: int):
        super().__init__(ref, worksheet)
        self.row_index = row_index
        self.update()

    def get_data(self, wh: gspread.Worksheet):
        return wh.row_values(self.row_index)

    def get_news(self, new_data: List) -> None:
        self.answer = ''
        if len(new_data) != len(self.data):
            self.answer += (f"Изменен размер строки {self.row_index} с {len(self.data)}" +
                            f" на {len(new_data)}\n")
        col_index = 1
        for i, j in zip(self.data, new_data):
            if i != j:
                self.answer += (f"Изменена ячейка с координатами ({self.row_index}, {col_index}) "
                                + f"c {i} на {j}\n")
            col_index += 1


class ColChecker(BaseChecker):
    col_index: int

    def __init__(self, ref: str, worksheet: int, col_index: int):
        super().__init__(ref, worksheet)
        self.col_index = col_index
        self.update()

    def get_data(self, wh: gspread.Worksheet):
        return wh.col_values(self.col_index)

    def get_news(self, new_data: List) -> None:
        self.answer = ''
        if len(new_data) != len(self.data):
            self.answer += (f"Изменен размер столбца {self.col_index} с {len(self.data)}" +
                            f" на {len(new_data)}\n")
        row_index = 1
        for i, j in zip(self.data, new_data):
            if i != j:
                self.answer += (f"Изменена ячейка с координатами ({self.col_index}, {row_index}) "
                                + f"c {i} на {j}\n")
            row_index += 1


class SheetChecker(BaseChecker):
    def __init__(self, ref: str, worksheet: int):
        super().__init__(ref, worksheet)
        self.update()

    def get_data(self, wh: gspread.Worksheet):
        return wh.get_all_values()

    def get_news(self, new_data: List) -> None:
        self.answer = ''
        if len(new_data) != len(self.data):
            self.answer += (f"Изменен размер таблицы по вертикали с {len(self.data)}" +
                            f" на {len(new_data)}\n")
        if len(new_data[0]) != len(self.data[0]):
            self.answer += (f"Изменен размер таблицы по горизонтали с {len(self.data)}" +
                            f" на {len(new_data)}\n")
        row_index = col_index = 1
        for row_1, row_2 in zip(self.data, new_data):
            for i, j in zip(row_1, row_2):
                if i != j:
                    self.answer += (f"Изменена ячейка с координатами ({col_index}, {row_index}) "
                                    + f"c {i} на {j}\n")
                col_index += 1
            row_index += 1

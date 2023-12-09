"""Helpers for commands."""

from enum import Enum
from typing import Any, Dict, List, Tuple, Union

from django.core.management.base import OutputWrapper

# TODO: Add tests for this class


class Table:
    """A class for rendering a table on the terminal."""

    class Alignment(str, Enum):
        """An alignment of a column."""

        LEFT = "left"
        RIGHT = "right"

        @property
        def to_f(self) -> str:
            """Return as symbol for f-strings"""
            if self is self.LEFT:
                return "<"

            if self is self.RIGHT:
                return ">"

            raise NotImplementedError("Invalid alignment")

    def __init__(self, default_alignment="left") -> None:
        self._rows: List[Tuple[str, ...]] = []
        self._column_width: Tuple[int, ...] = tuple()
        self._alignment: List[Table.Alignment] = []
        self._default_alignment = self.Alignment(default_alignment)

    def set_data(self, data: List[Dict[str, Any]]):
        """Set data of this table."""
        self._rows = self._convert_to_table(data)
        self._column_widths = self._calculate_column_width()
        self._reset_alignment()

    @property
    def columns_count(self) -> int:
        """Return number of columns."""
        return len(self._rows[0])

    def _convert_to_table(self, data: List[dict]) -> List[Tuple[str, ...]]:
        table = [tuple(self._format_head(v) for v in data[0].keys())]
        table += [tuple(self._format_value(v) for v in o.values()) for o in data]
        return table

    def _format_head(self, value: str) -> str:
        return value.replace("_", " ").capitalize()

    def _format_value(self, value) -> str:
        if value is None:
            return "?"

        if isinstance(value, float):
            return f"{value:,.1f}"

        if isinstance(value, int):
            return f"{value:,}"

        return str(value)

    def _calculate_column_width(self) -> Tuple[int, ...]:
        widths = [[] for _ in self._rows[0]]
        for row in self._rows:
            for col_num, column in enumerate(row):
                widths[col_num].append(len(column))

        max_width = tuple(max(column) for column in widths)
        return max_width

    def _reset_alignment(self):
        self._alignment = [self._default_alignment for _ in range(self.columns_count)]

    def set_alignment(self, column: int, alignment: Union[Alignment, str]):
        """Set alignment for a column."""
        self._alignment[column] = self.Alignment(alignment)

    def write(self, stdout: OutputWrapper, indentation: int = 2, margin: int = 2):
        """Write table to output."""
        self._write_table(stdout, indentation, margin)

    def _write_table(self, stdout: OutputWrapper, indentation: int, margin: int):
        columns_count = self.columns_count
        for row_num, row in enumerate(self._rows):
            output_row = " " * indentation
            for col_num, column in enumerate(row):
                width = self._column_widths[col_num]
                alignment = self._alignment[col_num]
                output_row += f"{column:{alignment.to_f}{width}}"

                if col_num < columns_count - 1:
                    output_row += " " * margin

            stdout.write(output_row)

            if row_num == 0:
                output_row = " " * indentation
                for col_num, _ in enumerate(row):
                    width = self._column_widths[col_num]
                    output_row += "-" * width + " " * margin
                stdout.write(output_row)

"""Tests for Table + subcomponents."""

from opentui.components import Box, Text
from startui.table import (
    Table,
    TableBody,
    TableCaption,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
)


class TestTable:
    def test_returns_box(self):
        assert isinstance(Table(), Box)

    def test_has_border(self):
        t = Table()
        assert t.border is True

    def test_children_passed_through(self):
        t = Table(TableHeader(), TableBody())
        assert len(t.get_children()) == 2


class TestTableHeader:
    def test_returns_box(self):
        assert isinstance(TableHeader(), Box)

    def test_row_direction(self):
        h = TableHeader(TableHead("Name"), TableHead("Age"))
        children = h.get_children()
        assert len(children) == 2


class TestTableBody:
    def test_returns_box(self):
        assert isinstance(TableBody(), Box)

    def test_rows(self):
        b = TableBody(
            TableRow(TableCell("Alice"), TableCell("30")),
            TableRow(TableCell("Bob"), TableCell("25")),
        )
        assert len(b.get_children()) == 2


class TestTableRow:
    def test_returns_box(self):
        assert isinstance(TableRow(), Box)

    def test_row_direction(self):
        r = TableRow(TableCell("a"), TableCell("b"))
        assert r._flex_direction == "row"


class TestTableHead:
    def test_returns_text(self):
        h = TableHead("Name")
        assert isinstance(h, Text)
        assert h._bold is True


class TestTableCell:
    def test_returns_text(self):
        c = TableCell("Value")
        assert isinstance(c, Text)


class TestTableCaption:
    def test_returns_text(self):
        c = TableCaption("Table 1")
        assert isinstance(c, Text)


class TestTableComposition:
    def test_full_table(self):
        table = Table(
            TableCaption("Users"),
            TableHeader(
                TableHead("Name"),
                TableHead("Age"),
            ),
            TableBody(
                TableRow(TableCell("Alice"), TableCell("30")),
                TableRow(TableCell("Bob"), TableCell("25")),
            ),
        )
        assert isinstance(table, Box)
        assert len(table.get_children()) == 3

import openpyxl


def get_table(tables: list[list], name: str) -> str:
    """
        Возвращает путь к файлу таблицы
    """
    wb = openpyxl.Workbook()
    sheet = wb.active

    for row in range(0, len(tables)):
        for column in range(0, len(tables[row])):
            c = sheet.cell(row=row + 1, column=column + 1)
            c.value = tables[row][column]
    wb.save(f'{name}.xlsx')
    return f'{name}.xlsx'

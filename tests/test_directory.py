"""Pruebas del directorio de empleados (solo lectura)."""


def test_employee_is_found_by_id_and_unknown_id_gives_none(directory):
    assert directory.get_employee("EMP-0004")["name"] == "Jorge Díaz"
    assert directory.get_employee("EMP-9999") is None


def test_department_search_ignores_case_and_accents(directory):
    expected = {"EMP-0001", "EMP-0003", "EMP-0004"}
    for spelling in ("Tecnología", "tecnologia", "TECNOLOGÍA"):
        found = directory.search_by_department(spelling)
        assert {item["id"] for item in found} == expected


def test_unknown_department_gives_empty_list(directory):
    assert directory.search_by_department("Marketing") == []
    assert "Finanzas" in directory.departments()

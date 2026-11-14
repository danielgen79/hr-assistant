"""Directorio de empleados de solo lectura."""

import json
import unicodedata
from pathlib import Path


def normalize(text):
    """Normaliza un texto: minusculas y sin tildes.

    :param text: Texto original
    :type text: str
    :return: Texto en minusculas y sin marcas diacriticas
    :rtype: str
    """
    decomposed = unicodedata.normalize("NFD", text.strip().lower())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


class Directory:
    """Consulta de empleados cargados una sola vez desde un archivo JSON.

    :param employees: Lista de empleados
    :type employees: list
    """

    def __init__(self, employees):
        self._employees = tuple(dict(item) for item in employees)

    @classmethod
    def load(cls, path):
        """Carga el directorio desde un archivo JSON.

        :param path: Ruta del archivo
        :type path: str
        :return: El directorio cargado
        :rtype: Directory
        """
        content = Path(path).read_text(encoding="utf-8")
        return cls(json.loads(content))

    def get_employee(self, employee_id):
        """Busca un empleado por id.

        :param employee_id: Id con forma ``EMP-0001``
        :type employee_id: str
        :return: El empleado o ``None`` si no existe
        :rtype: dict or None
        """
        wanted = str(employee_id).strip().upper()
        for item in self._employees:
            if item["id"].upper() == wanted:
                return dict(item)
        return None

    def search_by_department(self, department):
        """Lista los empleados de un departamento.

        :param department: Nombre, sin importar mayusculas ni tildes
        :type department: str
        :return: Empleados del departamento (vacia si no existe)
        :rtype: list
        """
        wanted = normalize(str(department))
        return [
            dict(item)
            for item in self._employees
            if normalize(item["department"]) == wanted
        ]

    def departments(self):
        """Devuelve los departamentos existentes, sin repetir.

        :return: Nombres de departamento en orden de aparicion
        :rtype: list
        """
        names = []
        for item in self._employees:
            if item["department"] not in names:
                names.append(item["department"])
        return names

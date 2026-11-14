"""Fixtures compartidas de las pruebas del HR Assistant."""

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

PRODUCT_DIR = Path(__file__).resolve().parents[1]
if str(PRODUCT_DIR) not in sys.path:
    sys.path.insert(0, str(PRODUCT_DIR))

# Importes despues de ajustar sys.path.
# pylint: disable=wrong-import-position
from helpers import (  # noqa: E402
    OTHER_API_KEY, OTHER_CLIENT, TEST_API_KEY, TEST_CLIENT,
)
from app.agent import Agent  # noqa: E402
from app.config import load_config  # noqa: E402
from app.directory import Directory  # noqa: E402
from app.llm import create_model  # noqa: E402
from app.main import create_app  # noqa: E402

EMPLOYEES_PATH = PRODUCT_DIR / "data" / "employees.json"


@pytest.fixture(name="employees_path")
def employees_path_fixture():
    """Ruta del archivo de empleados del producto."""
    return str(EMPLOYEES_PATH)


@pytest.fixture(name="directory")
def directory_fixture(employees_path):
    """Directorio real cargado desde los datos del producto."""
    return Directory.load(employees_path)


@pytest.fixture(name="make_agent")
def make_agent_fixture(directory):
    """Fabrica de agentes con el directorio real."""
    def make(model, max_steps=3):
        return Agent(model, directory, max_steps)

    return make


@pytest.fixture(name="build_client")
def build_client_fixture(employees_path, directory):
    """Fabrica de clientes de prueba con configuracion a medida.

    Recibe un dict de variables de entorno que se suma a la ruta de datos.
    Desde la sesion 4 la API siempre pide clave: por omision se configuran
    dos clientes de prueba y el cliente HTTP envia la clave del primero en
    ``X-API-Key``. Las pruebas pueden cambiar esto asi:

    - ``extra_env={"API_KEYS": ...}`` reemplaza los clientes configurados.
    - ``api_key=None`` no envia el encabezado (cada peticion lo decide).
    - ``api_key="otra"`` envia esa clave en todas las peticiones.
    - ``rate_clock`` es el reloj falso del limitador de peticiones.
    """
    def build(extra_env=None, model=None, api_key=TEST_API_KEY, rate_clock=None):
        env = {
            "EMPLOYEES_PATH": employees_path,
            "API_KEYS": (
                f"{TEST_CLIENT}:{TEST_API_KEY},{OTHER_CLIENT}:{OTHER_API_KEY}"
            ),
        }
        env.update(extra_env or {})
        config = load_config(env)
        chosen = model or create_model(config.model_provider, directory)
        application = create_app(
            config, chosen, directory, rate_clock=rate_clock
        )
        headers = {"X-API-Key": api_key} if api_key else {}
        return TestClient(application, headers=headers)

    return build


@pytest.fixture(name="client")
def client_fixture(build_client):
    """Cliente con la configuracion por omisión, el modelo simulado y clave."""
    return build_client()


@pytest.fixture(name="anonymous_client")
def anonymous_client_fixture(build_client):
    """Cliente que no envia ``X-API-Key`` (para probar el 401)."""
    return build_client(api_key=None)

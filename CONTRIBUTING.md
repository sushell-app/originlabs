# Contribuir a OriginLabs

¡Gracias por tu interés en **OriginLabs**! Este proyecto es open source bajo licencia **[GNU AGPL-3.0](LICENSE)**.

---

## Entorno de desarrollo local

Requisitos: **Docker** y **Docker Compose**.

```bash
cp .env.example .env
docker compose -f compose.dev.yml up --build -d
make migrate
```

- Panel React: `http://localhost`
- Documentación OpenAPI (desarrollo): `http://localhost/api/docs`

---

## Estándares de calidad y verificaciones

Antes de abrir un Pull Request, asegúrate de pasar los chequeos del repositorio:

### Backend (`backend/` · Python 3.12+ / FastAPI)
```bash
pip install -e ".[dev]"
ruff check .
mypy app
pytest
```
- Usa type hints estrictos y esquemas **Pydantic v2** para toda entrada externa.
- Nunca uses `shell=True` ni concatenes strings en SQL o comandos del sistema.

### Frontend (`frontend/` · React / TypeScript / Vite / Tailwind CSS)
```bash
npm install
npm run typecheck
npm run build
```
- Sigue la paleta oscura neutra y los patrones definidos en [docs/design-system.md](docs/design-system.md).

### Infraestructura e instalador
```bash
make check-compose
make check-bash
```

---

## Alcance de contribuciones

Consulta [README.md](README.md) y [docs/architecture.md](docs/architecture.md) para mantener alineadas las contribuciones con la arquitectura modular del núcleo y los estándares de [docs/security-sanitization.md](docs/security-sanitization.md).

Al enviar una contribución aceptas licenciar tu código bajo los términos de **GNU AGPL-3.0**.

# AI Core

AI Core will contain the independent AI service described in the architecture
documents. This initial structure keeps only stable project roots and leaves
internal package boundaries for later implementation issues.

## Project structure

```text
src/ai-core/
├── configs/                  # Versioned, non-secret runtime configuration
├── docs/                     # Architecture and implementation decisions
├── scripts/                  # Development and operational utilities
├── src/                      # Future AI Core source code
└── tests/                    # Future AI Core tests
```

This task intentionally defines no internal packages or test subdivisions.
Runtime code, dependencies, framework configuration, package boundaries, and
deployment configuration will be added by later issues when their requirements
are known.

## Документация

- [Архитектура генерации образов](docs/image-generation-architecture.md)
- [Выбор моделей и реализация ИИ-модуля](docs/model-selection-and-implementation.md)
- [Последовательность разработки](docs/development-roadmap.md)

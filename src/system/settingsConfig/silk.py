SILKY_PYTHON_PROFILER = True

SILKY_PYTHON_PROFILER_BINARY = True

SILKY_PYTHON_PROFILER_RESULT_PATH = "prof"

# Arquivos estáticos e de mídia não passam pelo silk: cada página carrega
# dezenas deles e o profiler somava ~40 ms a cada um (≈1 s por página no
# runserver, que atende uma requisição por vez).
ARQUIVOS_SEM_PROFILING = ("/media/", "/static/", "/favicon", "/serviceworker.js", "/manifest.json")


def _interceptar(request) -> bool:
    return not request.path.startswith(ARQUIVOS_SEM_PROFILING)


SILKY_INTERCEPT_FUNC = _interceptar

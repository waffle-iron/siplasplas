#include "runtimeloader.hpp"

using namespace cpp;
using namespace cpp::dynamic_reflection;

RuntimeLoader::RuntimeLoader(const DynamicLibrary& library)
{
    load(library);
}

void RuntimeLoader::load(const DynamicLibrary& library)
{
    _library = library;
    _runtime.reset(library.path());
    getRuntimeLoader().get<void(*)(void*)>()(&_runtime);
}

Runtime& RuntimeLoader::runtime()
{
    return _runtime;
}

DynamicLibrary::Symbol& RuntimeLoader::getRuntimeLoader()
{
    return _library->getSymbol("SIPLASPLAS_REFLECTION_LOAD_RUNTIME");
}

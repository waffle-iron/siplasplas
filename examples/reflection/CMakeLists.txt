add_subdirectory(plugininterface)
add_subdirectory(plugin)

function(add_reflection_example NAME)
    cmake_parse_arguments(ARGS
        ""
        ""
        "DEPENDS;INSTALL_SOURCES"
        ${ARGN}
    )

    list(APPEND ARGS_DEPENDS siplasplas-reflection)

    if(ARGS_INSTALL_SOURCES)
        set(install_sources INSTALL_SOURCES ${ARGS_INSTALL_SOURCES})
    endif()

    add_example(${NAME} DEPENDS ${ARGS_DEPENDS} ${install_sources} ${ARGS_UNPARSED_ARGUMENTS})
    reflection_target(examples-${NAME})
endfunction()

function(get_ram_mb RESULT)
    if(UNIX)
        execute_process(
            COMMAND grep MemTotal /proc/meminfo
            OUTPUT_VARIABLE stdout
        )

        if(stdout)
            string(REGEX REPLACE "MemTotal:(\ *)([0-9]+)kB" "\\2" totalKilobytes "${stdout}")
            math(EXPR totalMegabytes "${totalKilobytes} / (1024)")
            message(STATUS "Total RAM: ${totalMegabytes}MB")
            set(${RESULT} "${totalMegabytes}" PARENT_SCOPE)
        endif()
    else()
        set(${RESULT} 0 PARENT_SCOPE)
    endif()
endfunction()

get_ram_mb(RAMMB)
if(RAMMB GREATER 1024)
    add_reflection_example(chaiscript DEPENDS chaiscript INSTALL_SOURCES myclass.hpp)
endif()

add_reflection_example(reflection DEPENDS json4moderncpp INSTALL_SOURCES myclass.hpp)

# See issue #26
if(NOT SIPLASPLAS_CI_BUILD)
    add_example(plugin DEPENDS plugininterface siplasplas-reflection)
    # Force pluginexample to be built first, else the shared library
    # could not be loaded
    add_dependencies(examples-plugin pluginexample)
endif()
"""Tapify module, which can initialize a class or run a function by parsing arguments from the command line."""
from inspect import signature, Parameter
from typing import Any, Callable, List, Optional, Type, TypeVar, Union

from docstring_parser import parse

from tap import Tap

InputType = TypeVar("InputType")
OutputType = TypeVar("OutputType")


def tapify(
    class_or_function: Union[Callable[[InputType], OutputType], Type[OutputType]],
    known_only: bool = False,
    command_line_args: Optional[List[str]] = None,
    explicit_bool: bool = False,
    **func_kwargs,
) -> OutputType:
    """Tapify initializes a class or runs a function by parsing arguments from the command line.

    :param class_or_function: The class or function to run with the provided arguments.
    :param known_only: If true, ignores extra arguments and only parses known arguments.
    :param command_line_args: A list of command line style arguments to parse (e.g., ['--arg', 'value']).
                              If None, arguments are parsed from the command line (default behavior).
    :param explicit_bool: Booleans can be specified on the command line as "--arg True" or "--arg False"
                        rather than "--arg". Additionally, booleans can be specified by prefixes of True and False
                        with any capitalization as well as 1 or 0.
    :param func_kwargs: Additional keyword arguments for the function. These act as default values when
                        parsing the command line arguments and overwrite the function defaults but
                        are overwritten by the parsed command line arguments.
    """
    # Get signature from class or function
    sig = signature(class_or_function)

    # Parse class or function docstring in one line
    if isinstance(class_or_function, type) and class_or_function.__init__.__doc__ is not None:
        doc = class_or_function.__init__.__doc__
    else:
        doc = class_or_function.__doc__

    # Parse docstring
    docstring = parse(doc)

    # Get the description of each argument in the class init or function
    param_to_description = {param.arg_name: param.description for param in docstring.params}

    # Create a Tap object with a description from the docstring of the function or class
    description = "\n".join(filter(None, (docstring.short_description, docstring.long_description)))
    tap = Tap(description=description, explicit_bool=explicit_bool)

    # Keep track of whether **kwargs was provided
    has_kwargs = False

    # Add arguments of class init or function to the Tap object
    for param_name, param in sig.parameters.items():
        tap_kwargs = {}

        # Skip **kwargs
        if param.kind == Parameter.VAR_KEYWORD:
            has_kwargs = True
            known_only = True
            continue

        # Get type of the argument
        if param.annotation != Parameter.empty:
            # Any type defaults to str (needed for dataclasses where all non-default attributes must have a type)
            if param.annotation is Any:
                tap._annotations[param.name] = str
            # Otherwise, get the type of the argument
            else:
                tap._annotations[param.name] = param.annotation

        # Get the default or required of the argument
        if param.name in func_kwargs:
            tap_kwargs["default"] = func_kwargs[param.name]
            del func_kwargs[param.name]
        elif param.default != Parameter.empty:
            tap_kwargs["default"] = param.default
        else:
            tap_kwargs["required"] = True

        # Get the help string of the argument
        if param.name in param_to_description:
            tap.class_variables[param.name] = {"comment": param_to_description[param.name]}

        # Add the argument to the Tap object
        tap._add_argument(f"--{param_name}", **tap_kwargs)

    # If any func_kwargs remain, they are not used in the function, so raise an error
    if func_kwargs and not known_only:
        raise ValueError(f"Unknown keyword arguments: {func_kwargs}")

    # Parse command line arguments
    command_line_args = tap.parse_args(args=command_line_args, known_only=known_only)

    # Get command line arguments as a dictionary
    command_line_args_dict = command_line_args.as_dict()

    # Get **kwargs from extra command line arguments
    if has_kwargs:
        kwargs = {tap.extra_args[i].lstrip("-"): tap.extra_args[i + 1] for i in range(0, len(tap.extra_args), 2)}

        command_line_args_dict.update(kwargs)

    # Initialize the class or run the function with the parsed arguments
    return class_or_function(**command_line_args_dict)

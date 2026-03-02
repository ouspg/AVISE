"""
Unit tests for AVISE CLI
"""
from avise import cli, __version__
import pytest

SET_CONF_PATH = "avise/configs/SET//languagemodel/single_turn/prompt_injection_mini.json"
CONNECTOR_CONF_PATH = "avise/configs/connector/ollama.json"

test_incorrect_args_cases = [("--incorrectargument", "unrecognized argument"),
                             (f"--SET prompt_injection --connectorconf {CONNECTOR_CONF_PATH} --SETcof {SET_CONF_PATH}", "unrecognized argument")]
test_missing_args_cases=[(f"--SET prompt_injection --SETconf {SET_CONF_PATH}", "is required"),
                         (f"--connectorconf {CONNECTOR_CONF_PATH} --SETconf {SET_CONF_PATH}", "is required")]
test_arg_typos_cases=[(f"--SET prompt_injection --connectorconf this/file/should/not/exits.json --SETconf {SET_CONF_PATH}","FileNotFoundError"),
                      (f"--SET prompt_injection --connectorconf {CONNECTOR_CONF_PATH} --SETconf this/file/should/not/exist.json", "FileNotFoundError"),
                      ]
test_arg_datatypes_cases=[(123090, TypeError),
                          (123.231, TypeError),
                          ({"test": 123}, TypeError),
                          ((()), TypeError),
                          (False, TypeError),
                          (True, TypeError),
                          (None, TypeError)
                          ]
def test_version_command(capsys):
    """
    Test that the version command outputs correct version.
    """
    try:
        cli.main(["--version"])
    except SystemExit:
        pass
    captured = capsys.readouterr()
    #with capsys.disabled():
    #    print(f'captured.out: {captured.out}')
    assert __version__ in captured.out


def test_SET_list(capsys):
    """
    Test that SET_list command output is as expected.
    """
    try:
        cli.main(["--SET_list"])
    except SystemExit:
        pass
    captured = capsys.readouterr()
    #with capsys.disabled():
    #    print(f'captured.out: {captured.out}')
    # Add strings from expected SET_list output here
    assert "prompt_injection" in captured.out

def test_too_long_arg():
    """
    Test that output is as expected when CLI receives a too long argument.
    """
    test_input = [f"string{i}" for i in range(250)]

    with pytest.raises(ValueError):
        cli.main(test_input)


@pytest.mark.parametrize("test_input, expected_output", test_incorrect_args_cases)
def test_incorrect_args(capsys, test_input, expected_output):
    """
    Tests if CLI can handle incorrect arguments.
    """
    test_inputs = test_input.split()
    try:
        cli.main(test_inputs)
    except SystemExit:
        pass
    captured = capsys.readouterr()

    assert expected_output in captured.err

@pytest.mark.parametrize("test_input,expected_output", test_missing_args_cases)
def test_missing_args(capsys, test_input, expected_output):
    """
    Tests if CLI can handle missing arguments.
    """
    test_inputs = test_input.split()
    try:
        cli.main(test_inputs)
    except SystemExit:
        pass
    captured = capsys.readouterr()
    assert expected_output in captured.out

@pytest.mark.parametrize("test_input,expected_output", test_arg_datatypes_cases)
def test_arg_datatypes(test_input, expected_output):
    """
    Tests if CLI can handle unexpected datatypes as inputs.
    """
    with pytest.raises(TypeError):
        cli.main(test_input)


@pytest.mark.parametrize("test_input,expected_output", test_arg_typos_cases)
def test_arg_typos(capsys, test_input, expected_output):
    """
    Tests if CLI can handle typos in arguments as expected.
    """
    test_inputs = test_input.split()

    with pytest.raises(FileNotFoundError):
        cli.main(test_inputs)


def test_SET_runner(capsys):
    """
    Test that SETrunner executes succesfully.
    Uses prompt_injection SET.
    """
    cli.main(["--SET", "prompt_injection", "--connectorconf", CONNECTOR_CONF_PATH, "--SETconf", SET_CONF_PATH])
    captured = capsys.readouterr()
    #with capsys.disabled():
    #    print(f'captured.out: {captured.out}')
    assert "Security Evaluation Test completed!" in captured.out

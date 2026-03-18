from agentmux.main import main


def test_main(capsys) -> None:
    main()
    captured = capsys.readouterr()
    assert captured.out.strip() == "hello from agentmux"

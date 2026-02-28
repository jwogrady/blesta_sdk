# Blesta Python SDK

The **Blesta Python SDK** offers an intuitive API and CLI interface for seamless interaction with Blesta's REST API.

Requires **Python >= 3.9**.

## 🚀 Quick and Easy Setup

1. **Create a Project Folder:**
   ```bash
   mkdir my_project && cd my_project
   ```

2. **Install Blesta SDK:**

   Using uv (recommended):
   ```bash
   uv init && uv add blesta_sdk
   ```

   Using pip:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows, use venv\Scripts\activate
   pip install blesta_sdk
   ```

3. **Configure API Credentials:**

   Generate API credentials in Blesta's staff area and save them in a `.env` file in your project's root folder:

   ```env
   BLESTA_API_URL=https://your-blesta-domain.com/api
   BLESTA_API_USER=your_api_user
   BLESTA_API_KEY=your_api_key
   ```

  That's it. Let's roll!

## 📖 Usage Examples

### Python API

```python
from blesta_sdk.api import BlestaRequest

api = BlestaRequest("https://your-blesta-domain.com/api", "your_user", "your_key")

# GET request
response = api.get("clients", "getList", {"status": "active"})
if response.response_code == 200:
    print(response.response)  # parsed JSON "response" field
else:
    print(response.errors())

# POST request
response = api.post("clients", "create", {"firstname": "John", "lastname": "Doe"})

# PUT request
response = api.put("clients", "edit", {"client_id": 1, "firstname": "Jane"})

# DELETE request
response = api.delete("clients", "delete", {"client_id": 1})

# Inspect the last request made
print(api.get_last_request())  # {"url": "...", "args": {...}}
```

### CLI

#### General Command Structure

```bash
blesta --model <model_name> --method <method_name> [--action GET] [--params key=value key2=value2] [--last-request]
```

- **`--model`**: The API model to interact with (e.g., `clients`, `services`).
- **`--method`**: The method to call on the specified model (e.g., `getList`, `get`, `getCustomFields`).
- **`--action`**: The HTTP action to perform (default is `GET`).
- **`--params`**: Optional parameters to pass to the method (e.g., `key=value` pairs).
- **`--last-request`**: Displays the URL and parameters of the request that was just made.

The CLI reads `BLESTA_API_URL`, `BLESTA_API_USER`, and `BLESTA_API_KEY` from a `.env` file in the current directory.

#### Clients Model ([API Documentation](https://source-docs.blesta.com/class-Clients.html))

- **List all active clients:**
  ```bash
  blesta --model clients --method getList --params status=active --last-request
  ```

- **Get details of a specific client:**
  ```bash
  blesta --model clients --method get --params client_id=1 --last-request
  ```

#### Services Model ([API Documentation](https://source-docs.blesta.com/class-Services.html))

- **List all active services:**
  ```bash
  blesta --model services --method getList --params status=active --last-request
  ```

- **Count the active services for a client:**
  ```bash
  blesta --model services --method getListCount --params client_id=1 status=active
  ```

- **List all services for a client:**
  ```bash
  blesta --model services --method getAllByClient --params client_id=1 status=active --last-request
  ```

## 📂 Project Structure

Here's an overview of the project structure:

```
.
├── .github
│   └── workflows
│       └── publish.yml
├── CHANGELOG.md
├── LICENSE
├── README.md
├── examples
│   └── examples.sh
├── pyproject.toml
├── src
│   └── blesta_sdk
│       ├── __init__.py
│       ├── api
│       │   ├── __init__.py
│       │   └── blesta_request.py
│       ├── cli
│       │   ├── __init__.py
│       │   └── blesta_cli.py
│       └── core
│           ├── __init__.py
│           └── blesta_response.py
├── tests
│   ├── __init__.py
│   └── test_blesta_sdk.py
└── uv.lock
```

- **CHANGELOG.md**: Version history and release notes.
- **LICENSE**: The license file for the project.
- **README.md**: The main documentation file for the project.
- **examples/**: Contains example scripts and usage.
- **pyproject.toml**: Configuration file for the project.
- **src/**: The source code for the Blesta SDK.
  - **blesta_sdk/**: The main package for the SDK.
    - **api/**: API request handling (`BlestaRequest`).
    - **cli/**: Command-line interface implementation.
    - **core/**: Response handling (`BlestaResponse`).
- **tests/**: Unit tests for the SDK.
- **uv.lock**: Lock file for dependencies.

## 🤝 Contribution

We welcome contributions! Whether it's a feature request, bug report, or pull request, we appreciate your input.

### How to Contribute

1. **Fork the repository.**
2. **Create a feature branch:**
   ```bash
   git checkout -b feature/your-feature-name
   ```
3. **Commit your changes:**
   ```bash
   git commit -m "Add your feature description here"
   ```
4. **Push to your branch:**
   ```bash
   git push origin feature/your-feature-name
   ```
5. **Open a pull request:**
   - Push your branch to GitHub.
   - Go to the repository on GitHub.
   - Click on the "Pull requests" tab.
   - Click "New pull request".
   - Select your branch and the main branch.
   - Add a descriptive title and detailed description.
   - Click "Create pull request".

---

This project is licensed under the [MIT License](LICENSE)

Happy coding! 🎉

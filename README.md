# Blesta Python SDK

The **Blesta Python SDK** offers an intuitive API and CLI interface for seamless interaction with Blesta's REST API.

## 🚀 Quick and Easy Setup

1. **Create a Project Folder:**
   ```bash
   mkdir my_project && cd my_project
   ```

2. **Set Up a Python Virtual Environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows, use venv\Scripts\activate
   ```

3. **Install Blesta SDK:**
   ```bash
   pip install blesta_sdk
   ```

4. **Configure API Credentials:**

   Generate API credentials in Blesta's staff area and save them in a `.env` file in your project's root folder:

   ```env
   BLESTA_API_URL=https://your-blesta-domain.com/api
   BLESTA_API_USER=your_api_user
   BLESTA_API_KEY=your_api_key
   ```

  That's it. Let's roll!

## 📖 Usage Examples

### General Command Structure

```bash
blesta-cli --model <model_name> --method <method_name> [--action GET] [--params key=value key2=value2] [--last-request]
```

- **`--model`**: The API model to interact with (e.g., `clients`, `services`).
- **`--method`**: The method to call on the specified model (e.g., `getList`, `get`, `getCustomFields`).
- **`--action`**: The HTTP action to perform (default is `GET`).
- **`--params`**: Optional parameters to pass to the method (e.g., `key=value` pairs).
- **`--last-request`**: Repeats the last request made.

### Clients Model ([API Documentation](https://source-docs.blesta.com/class-Clients.html))

- **List all active clients:**
  ```bash
  blesta-cli --model clients --method getList --params status=active --last-request
  ```

- **Get details of a specific client:**
  ```bash
  blesta-cli --model clients --method get --params client_id=1 --last-request
  ```

### Services Model ([API Documentation](https://source-docs.blesta.com/class-Services.html))

- **List all active services:**
  ```bash
  blesta-cli --model services --method getList --params status=active --last-request
  ```

- **Count the active services for a client:**
  ```bash
  blesta-cli --model services --method getListCount --params client_id=1 status=active
  ```

- **List all services for a client:**
  ```bash
  blesta-cli --model services --method getAllByClient --params client_id=1 status=active --last-request
  ```

## 📂 Project Structure

Here's an overview of the project structure:

```
.
├── LICENSE
├── README.md
├── examples
│   └── examples.sh
├── pyproject.toml
├── src
│   └── blesta_sdk
│       ├── __init__.py
│       ├── core
│       │   ├── __init__.py
│       │   └── blesta_response.py
│       ├── api
│       │   ├── __init__.py
│       │   └── blesta_request.py
│       └── cli
│           ├── __init__.py
│           └── blesta_cli.py
├── tests
│   ├── __init__.py
│   └── test_blesta_sdk.py
└── uv.lock
```

- **LICENSE**: The license file for the project.
- **README.md**: The main documentation file for the project.
- **examples/**: Contains example scripts and usage.
- **pyproject.toml**: Configuration file for the project.
- **src/**: The source code for the Blesta SDK.
  - **blesta_sdk/**: The main package for the SDK.
    - **core/**: Core functionality and response handling.
    - **api/**: API request handling.
    - **cli/**: Command-line interface implementation.
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

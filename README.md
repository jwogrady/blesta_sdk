# Blesta Python SDK

Blesta Python SDK provides both a API and CLI for Blesta's REST APi.

## Quick and Easy Setup

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
   pip install blesta_cli
   ```

4. **Configure API Credentials:**  
Admins, log in to Blesta's staff area to generate API credentials. You will need to paste the appropriate vales into the `.env` file that should be placed in this project's root folder. `.env` should look like this:

> ```env
> BLESTA_API_URL=https://your-blesta-domain.com/api
> BLESTA_API_USER=your_api_user
> BLESTA_API_KEY=your_api_key
> ```

That's it. Let's roll!

## Usage Examples

### General Command Structure

```bash
python blesta_cli.py --model <model_name> --method <method_name> [--action GET] [--params key=value key2=value2] [--last-request]
```

- **--model:** The API model to interact with (e.g., clients, services).  
- **--method:** The method to call on the specified model (e.g., getList, get, getCustomFields).  
- **--action:** The HTTP action to perform (default is GET).  
- **--params:** Optional parameters to pass to the method (e.g., key=value pairs).  
- **--last-request:** Repeats the last request made.  

### Clients Model ([Documentation](https://source-docs.blesta.com/class-Clients.html))

- **List all clients:**  
  ```bash
  python blesta_cli.py --model clients --method getList
  ```

- **Get details of a specific client:**  
  ```bash
  python blesta_cli.py --model clients --method get --params id=1
  ```
### Services Model ([Documentation](https://source-docs.blesta.com/class-Services.html))

- **List all services:**  
  ```bash
  python blesta_cli.py --model services --method getList
  ```

- **Get details of a specific service:**  
  ```bash
  python blesta_cli.py --model services --method get --params id=1
  ```

- **List all services for a client:**  
  ```bash
  python blesta_cli.py --model services --method getAll --params client_id=1
  ```

## Contribution

Contributions are welcome! Please submit a pull request or open an issue for feature requests or bug reports.

Happy Coding!

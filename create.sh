#!/bin/bash

# Script to create the directory structure and empty files for the ai-project-analizer

# Define the root project directory name
PROJECT_NAME="ai-project-analizer"


# Create top-level files
echo "Creating top-level files..."
touch .dockerignore
touch .gitignore
touch .env.sample
touch beeai.yaml
touch Dockerfile
touch docker-compose.yml
touch LICENSE
touch README.md
touch CHANGELOG.md
touch install.sh
touch start.sh
touch requirements.txt
touch requirements_dev.txt
touch app.py

# Create src directory and its contents
echo "Creating src directory and files..."
mkdir -p src
touch src/__main__.py
touch src/config.py
touch src/main.py
touch src/workflows.py

# Create src/agents directory and its files
echo "Creating src/agents directory and files..."
mkdir -p src/agents
touch src/agents/__init__.py
touch src/agents/zip_validator_agent.py
touch src/agents/extraction_agent.py
touch src/agents/tree_builder_agent.py
touch src/agents/file_triage_agent.py
touch src/agents/file_analysis_agent.py
touch src/agents/summary_synthesizer_agent.py

# Create src/tools directory and its files
echo "Creating src/tools directory and files..."
mkdir -p src/tools
touch src/tools/__init__.py
touch src/tools/file_io_tool.py
touch src/tools/rich_printer_tool.py

# Create src/utils directory and its files
echo "Creating src/utils directory and files..."
mkdir -p src/utils
touch src/utils/encoding_helper.py
touch src/utils/language_detector.py

# Create static directory and its files
echo "Creating static directory and files..."
mkdir -p static
touch static/style.css
touch static/app.js

# Create templates directory and its files
echo "Creating templates directory and files..."
mkdir -p templates
touch templates/upload.html
touch templates/result.html

# Create tests directory and its files
echo "Creating tests directory and files..."
mkdir -p tests
touch tests/__init__.py # Added __init__.py as it's common for test packages
touch tests/test_zip_validator.py
touch tests/test_file_analysis.py
touch tests/test_workflow_e2e.py

# Create docs directory and its files
echo "Creating docs directory and files..."
mkdir -p docs
touch docs/architecture.md
touch docs/api.md

# Create assets directory and its files
echo "Creating assets directory and files..."
mkdir -p assets
touch assets/workflow.png
touch assets/demo.gif

# Return to the original directory
cd ..

echo ""
echo "Project structure for '${PROJECT_NAME}' created successfully!"
echo "Remember to make shell scripts executable:"
echo "  chmod +x ${PROJECT_NAME}/install.sh"
echo "  chmod +x ${PROJECT_NAME}/start.sh"
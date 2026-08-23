# Architecture: Clone of Emergent.sh using NVIDIA NIM as Inference Engine

## Components

### Frontend (React/TypeScript)
- User Interface Layer
- Handles user prompts, displays generated apps, manages sessions
- Communicates with Backend API via REST/GraphQL
- Key components: AppBuilderUI, PromptEditor, AppPreview, ProjectDashboard

### Backend (Python FastAPI)
- API Gateway Layer
- Routes requests to appropriate services
- Handles authentication, rate limiting, request validation
- Exposes REST endpoints for frontend communication

### NIM Client Service
- NVIDIA NIM Integration Layer
- Manages API communication with NVIDIA NIM endpoints
- Handles authentication, token management, request/response processing
- Key endpoints: /v1/chat/completions, /v1/models

### Code Generation Service
- AI Orchestration Layer
- Processes user prompts into structured instructions
- Coordinates with NIM Client for LLM inference
- Generates code artifacts (frontend, backend, database schemas)

### Validation Service
- Quality Assurance Layer
- Validates generated code for syntax and security
- Runs unit tests on generated components
- Reports issues back to generation pipeline

### Deployment Service
- Infrastructure Layer
- Packages generated apps for deployment
- Manages cloud provider integrations
- Handles app lifecycle (deploy, update, delete)

### Database Layer
- Persistence Layer
- Stores user projects, prompts, generated code
- Manages metadata and versioning
- Supports rollback and history tracking

## Data Flow

1. User enters natural language prompt in Frontend
2. Frontend sends prompt to Backend API
3. Backend routes to Code Generation Service
4. Code Generation Service formats prompt for NIM Client
5. NIM Client sends request to NVIDIA NIM /v1/chat/completions endpoint
6. NIM returns generated code/response
7. Code Generation Service processes response into structured artifacts
8. Validation Service checks generated code quality
9. Validated code stored in Database Layer
10. Deployment Service packages and deploys app
11. Deployment status returned to Frontend for user feedback

## Interface Stubs

### NIM API Client Interface
```python
class NIMClient:
    def __init__(self, api_key: str, base_url: str):
        self.api_key = api_key
        self.base_url = base_url

    def chat_completion(self, messages: List[Dict], model: str = None) -> Dict:
        '''Send chat completion request to NVIDIA NIM'''
        pass

    def get_models(self) -> List[str]:
        '''Get available models from NIM'''
        pass
```

### Backend API Endpoints
```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List
from datetime import datetime

class PromptRequest(BaseModel):
    prompt: str
    user_id: str
    app_type: str = 'web'
    created_at: datetime = None

class AppResponse(BaseModel):
    app_id: str
    status: str
    preview_url: str
    generated_at: datetime
```

### Frontend Component Interface
```python
class AppBuilderUIProps:
    onPromptSubmit: Callable[[str], None]
    isLoading: bool
    projects: List[Dict]
```

### API Service Layer
```python
class APIService:
    BASE_URL: str = '/api/v1'

    def create_app(self, prompt: str, app_type: str) -> AppResponse:
        pass

    def get_app(self, app_id: str) -> Dict:
        pass

    def list_projects(self, user_id: str) -> List[Dict]:
        pass

    def deploy_app(self, app_id: str) -> Dict:
        pass
```

### NIM Client Configuration
```python
class NIMConfig:
    api_key: str = os.getenv('NVIDIA_API_KEY')
    base_url: str = 'https://api.nv.nvidia.com/v1'
    default_model: str = 'nvidia/llama-3.1-nim-70b'
    timeout: int = 30
    max_tokens: int = 4096
    temperature: float = 0.7
    stream: bool = False
```
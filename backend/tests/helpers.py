def auth_header(token: str):
    return {"Authorization": f"Bearer {token}"}

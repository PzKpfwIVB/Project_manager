from fastapi import Form


class SignupForm:
    def __init__(
            self,
            username: str = Form(...),
            password: str = Form(...),
            email: str = Form(default=''),
            full_name: str = Form(default='')
    ):
        self.username = username
        self.password = password
        self.email = email
        self.full_name = full_name

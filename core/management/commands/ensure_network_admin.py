import os
import sys
from getpass import getpass

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Garante que exista um administrador ativo para acessar a aplicação."

    def add_arguments(self, parser):
        parser.add_argument(
            "--check",
            action="store_true",
            help="Somente verifica a existência de um administrador válido.",
        )
        parser.add_argument(
            "--from-environment",
            action="store_true",
            help=(
                "Cria o administrador sem interação usando as variáveis "
                "DJANGO_SUPERUSER_USERNAME, DJANGO_SUPERUSER_EMAIL e "
                "DJANGO_SUPERUSER_PASSWORD."
            ),
        )

    def handle(self, *args, **options):
        user_model = get_user_model()
        administrators = user_model.objects.filter(
            is_active=True,
            is_superuser=True,
        )
        if any(user.has_usable_password() for user in administrators):
            self.stdout.write(self.style.SUCCESS("Administrador configurado."))
            return

        if options["check"]:
            raise CommandError("Nenhum administrador ativo com senha foi configurado.")

        if options["from_environment"]:
            self._create_from_environment(user_model)
            return

        if not sys.stdin.isatty():
            raise CommandError(
                "Execute este comando em um terminal interativo para criar "
                "o primeiro administrador."
            )

        self.stdout.write("Crie o primeiro administrador do Gestor Elétrico.")
        self.stdout.write("A senha não será exibida enquanto você digita.")

        while True:
            username = input("Usuário [admin]: ").strip() or "admin"
            email = input("E-mail (opcional): ").strip()
            candidate = user_model(username=username, email=email)

            try:
                self._validate_candidate(candidate)
            except ValidationError as error:
                self.stderr.write(
                    self.style.ERROR(self._format_validation_error(error))
                )
                continue

            password = getpass("Senha: ")
            confirmation = getpass("Confirme a senha: ")
            if password != confirmation:
                self.stderr.write(self.style.ERROR("As senhas não coincidem."))
                continue

            try:
                validate_password(password, user=candidate)
            except ValidationError as error:
                self.stderr.write(
                    self.style.ERROR(self._format_validation_error(error))
                )
                continue

            self._create_superuser(
                user_model,
                username,
                email,
                password,
            )
            return

    def _create_from_environment(self, user_model):
        username = os.getenv("DJANGO_SUPERUSER_USERNAME", "").strip() or "admin"
        email = os.getenv("DJANGO_SUPERUSER_EMAIL", "").strip()
        password = os.getenv("DJANGO_SUPERUSER_PASSWORD", "")
        if not password:
            raise CommandError(
                "Nenhum administrador foi migrado. Defina "
                "DJANGO_SUPERUSER_PASSWORD para criar o primeiro acesso."
            )

        candidate = user_model(username=username, email=email)
        try:
            self._validate_candidate(candidate)
            validate_password(password, user=candidate)
        except ValidationError as error:
            raise CommandError(self._format_validation_error(error)) from error

        self._create_superuser(
            user_model,
            username,
            email,
            password,
        )

    @staticmethod
    def _validate_candidate(candidate):
        candidate.full_clean(
            exclude=(
                "password",
                "last_login",
                "date_joined",
                "groups",
                "user_permissions",
            )
        )

    def _create_superuser(self, user_model, username, email, password):
        user_model.objects.create_superuser(
            username=username,
            email=email,
            password=password,
        )
        self.stdout.write(
            self.style.SUCCESS(f"Administrador '{username}' criado com sucesso.")
        )

    @staticmethod
    def _format_validation_error(error):
        return " ".join(error.messages)

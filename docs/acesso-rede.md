# Acesso pela rede local e pelo Tailscale

O modo de rede executa o Django com Waitress em `0.0.0.0:8010`. Os hosts
permitidos são montados a cada inicialização com os IPs realmente encontrados;
nenhum curinga é usado.

## Endereços detectados nesta máquina

- Neste computador: `http://127.0.0.1:8010/`
- Rede local: `http://192.168.0.34:8010/`
- Tailscale: `http://100.118.116.94:8010/`

O IP da rede local pode mudar quando o roteador renovar o DHCP. O inicializador
sempre mostra os endereços atuais antes de subir o servidor.

## Preparação única

Instale ou atualize as dependências:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Abra o PowerShell como administrador na pasta do projeto e crie as duas regras
de entrada:

```powershell
.\scripts\Manage-FirewallRule.ps1 -Action Add
```

As regras são limitadas da seguinte forma:

- LAN: TCP `8010`, somente perfis Privado/Domínio e origem `LocalSubnet`.
- Tailscale: TCP `8010`, somente origem `100.64.0.0/10`.

O script não altera outras regras e pode ser executado novamente com segurança.

## Iniciar

Execute:

```powershell
.\scripts\Start-NetworkServer.ps1
```

Ou dê duplo clique em `scripts\Iniciar-Gestor-Rede.cmd`.

O inicializador:

1. recusa iniciar se a porta estiver ocupada;
2. detecta os IPs LAN e Tailscale;
3. cria uma chave secreta persistente em `database/.network-secret`;
4. aplica migrações e verifica o Django;
5. garante que exista um administrador com senha;
6. coleta os arquivos estáticos;
7. inicia o Waitress e mostra todas as URLs.

Na primeira execução normal, informe no próprio terminal o nome de usuário,
e-mail opcional e uma senha forte. A senha não aparece durante a digitação e
não é gravada em arquivo ou histórico de comandos. Os próximos acessos usam
essa mesma conta.

Use `Ctrl+C` para encerrar. O computador servidor precisa permanecer ligado e
sem suspensão enquanto a aplicação estiver sendo utilizada.

Para executar apenas as verificações, sem iniciar o servidor:

```powershell
.\scripts\Start-NetworkServer.ps1 -PreflightOnly
```

Se ainda não houver administrador, a pré-verificação mostrará um aviso. A
criação acontecerá somente ao iniciar sem `-PreflightOnly`.

## Firewall

Consultar o estado:

```powershell
.\scripts\Manage-FirewallRule.ps1 -Action Status
```

Remover somente as regras desta aplicação:

```powershell
.\scripts\Manage-FirewallRule.ps1 -Action Remove
```

Se escolher outra porta, informe o mesmo valor nos dois scripts:

```powershell
.\scripts\Manage-FirewallRule.ps1 -Action Add -Port 8011
.\scripts\Start-NetworkServer.ps1 -Port 8011
```

## Tailscale

O outro dispositivo precisa estar conectado ao mesmo tailnet e autorizado pela
política de acesso do Tailscale para a porta `8010`. Não é necessário abrir
porta no roteador e não se deve habilitar Tailscale Funnel para esta aplicação.

Em caso de falha, teste no outro computador:

```powershell
tailscale ping 100.118.116.94
Test-NetConnection 100.118.116.94 -Port 8010
```

## Segurança

O modo de rede usa `DEBUG=False`, uma chave secreta aleatória persistente,
hosts explícitos, login obrigatório e firewall com origens limitadas. Todas as
telas operacionais, importações e documentos exigem autenticação.

Use uma senha exclusiva e mantenha o acesso limitado a dispositivos
confiáveis. Nunca encaminhe a porta `8010` no roteador.

Para alterar a senha, use o botão de chave no topo da aplicação. Se perder o
acesso, execute localmente:

```powershell
.\.venv\Scripts\python.exe manage.py changepassword NOME_DO_USUARIO
```

O acesso LAN direto usa HTTP. O acesso pelo IP Tailscale trafega dentro do túnel
do Tailscale, mas a URL exibida no navegador continuará começando com `http://`.

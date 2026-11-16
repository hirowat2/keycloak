# Consultar e remover acessos SSH por chave pública

Execute os comandos no servidor cujo acesso deseja administrar. Substitua `USUARIO` pelo nome da conta do servidor. Os exemplos pressupõem Linux com OpenSSH e chaves armazenadas no arquivo padrão `~/.ssh/authorized_keys`.

Cada linha desse arquivo autoriza uma chave pública a entrar naquela conta. A chave privada permanece com quem se conecta.

## 1. Localizar e consultar as chaves autorizadas

Procure os arquivos nas pastas de usuários e na pasta de root:

```bash
sudo find /home /root -type f -name "authorized_keys" \
  -exec printf '\nArquivo: %s\n' {} \; \
  -exec cat {} \;
```

Esse comando apenas consulta os arquivos. Cada `-exec` termina com `\;`.

Para consultar uma conta específica com números de linha:

```bash
sudo nl -ba /home/USUARIO/.ssh/authorized_keys
```

Para consultar a conta root:

```bash
sudo nl -ba /root/.ssh/authorized_keys
```

Para mostrar as impressões digitais (fingerprints) das chaves de uma conta:

```bash
sudo ssh-keygen -lf /home/USUARIO/.ssh/authorized_keys
```

Compare com a impressão digital da chave pública de quem deve perder o acesso, executando na máquina que possui essa chave:

```bash
ssh-keygen -lf ~/.ssh/id_ed25519.pub
```

Adapte o nome do arquivo se necessário. O comentário ao final da linha, como um e-mail, é apenas uma identificação livre; confirme a chave pela impressão digital.

## 2. Criar um backup antes de alterar

Mantenha uma sessão administrativa aberta e confirme que possui outra forma de acesso ao servidor.

```bash
sudo cp -p /home/USUARIO/.ssh/authorized_keys \
  "/home/USUARIO/.ssh/authorized_keys.bak.$(date +%Y%m%d-%H%M%S)"
```

O backup permite restaurar o arquivo em caso de erro. Para root, use `/root/.ssh/authorized_keys` e o caminho correspondente para o backup.

## 3. Remover uma chave específica

Abra o arquivo da conta:

```bash
sudo nano /home/USUARIO/.ssh/authorized_keys
```

Apague a linha inteira correspondente à chave que deseja revogar. No nano, salve com `Ctrl+O`, confirme com `Enter` e saia com `Ctrl+X`.

Para root:

```bash
sudo nano /root/.ssh/authorized_keys
```

Se a mesma chave aparecer mais de uma vez ou em outras contas, remova todas as ocorrências que devem perder acesso. Preserve as chaves que ainda precisam acessar o servidor.

## 4. Remover todas as chaves de uma conta

Depois de criar o backup, este comando esvazia o arquivo e revoga todas as chaves nele cadastradas:

```bash
sudo truncate -s 0 /home/USUARIO/.ssh/authorized_keys
```

Para revogar todas as chaves do arquivo de root:

```bash
sudo truncate -s 0 /root/.ssh/authorized_keys
```

Execute somente o comando correspondente à conta desejada. Isso não remove a conta nem desativa outras formas de autenticação, como senha.

## 5. Validar a alteração

Consulte novamente o arquivo e suas impressões digitais:

```bash
sudo nl -ba /home/USUARIO/.ssh/authorized_keys
sudo ssh-keygen -lf /home/USUARIO/.ssh/authorized_keys
```

Se o arquivo estiver vazio, `ssh-keygen` pode informar que ele não é um arquivo de chave pública válido.

Em outro terminal, teste a chave revogada a partir da máquina que possui a chave privada correspondente:

```bash
ssh -o ControlMaster=no -o ControlPath=none \
  -o IdentitiesOnly=yes -o IdentityAgent=none \
  -o PreferredAuthentications=publickey -o PasswordAuthentication=no \
  -i ~/.ssh/id_ed25519 USUARIO@SERVIDOR
```

Substitua `SERVIDOR` pelo endereço do servidor e ajuste o caminho da chave privada. O teste deve falhar para a chave revogada. Essas opções evitam reutilizar uma conexão existente e restringem o teste à identidade indicada, sem autenticação por senha.

Teste também uma chave administrativa que deve continuar funcionando antes de fechar sua sessão atual. Não é necessário reiniciar o serviço SSH após alterar `authorized_keys`.

## 6. Restaurar o backup, se necessário

Use o nome real do backup criado na etapa 2:

```bash
sudo cp -p /home/USUARIO/.ssh/authorized_keys.bak.AAAAMMDD-HHMMSS \
  /home/USUARIO/.ssh/authorized_keys
```

Restaurar o backup também restaura as autorizações das chaves que estavam nele.

## Limites da revogação

- Remover uma chave impede novas autenticações por aquela entrada; não encerra sessões SSH já abertas.
- A busca em `/home` e `/root` não cobre contas com diretórios pessoais em outros locais.
- O servidor pode usar outros arquivos de chaves, comandos externos, certificados SSH ou regras por usuário. Confira as configurações `AuthorizedKeysFile`, `AuthorizedKeysCommand`, `TrustedUserCAKeys` e blocos `Match` se o acesso continuar funcionando.
- Ferramentas de automação ou de gerenciamento do servidor podem recriar as chaves. Atualize também a origem dessas configurações quando aplicável.

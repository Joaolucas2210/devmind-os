---
name: generic-implementation
description: Use after discovery and planning to create a dedicated feature branch and implement minimal, safe, maintainable code changes.
---

# Generic Implementation

Use somente após discovery e planning.

## Branch de feature

Antes de alterar arquivos para uma nova feature:

1. Inspecionar o estado atual com `git status --short --branch`.
2. Identificar a branch de integração definida pelo projeto. Usar `develop` quando o repositório adotar GitFlow; caso contrário, seguir a convenção documentada no repositório.
3. Confirmar que mudanças locais existentes pertencem à mesma feature. Não fazer stash, descartar mudanças ou trocar de branch silenciosamente quando houver alterações não relacionadas.
4. Criar uma branch dedicada a partir da branch de integração com `git switch -c feature/<slug>`.
5. Usar um `<slug>` curto, descritivo, em minúsculas e separado por hífens.
6. Informar ao usuário o nome da branch criada antes de implementar.

Se a branch da feature já existir, reutilizá-la somente quando ela pertencer ao mesmo trabalho. Não executar `pull`, rebase, merge, push ou exclusão de branches sem necessidade ou autorização.

## Regras

- Fazer menor diff possível.
- Preservar comportamento existente.
- Seguir padrões do projeto.
- Evitar refatoração ampla.
- Adicionar testes quando houver regra de negócio.
- Não adicionar dependências sem necessidade.
- Não expor secrets ou PII.

## Saída esperada

- Alterações feitas
- Arquivos alterados
- Observações técnicas

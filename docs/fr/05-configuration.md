# 5 · Référence de configuration

> 🇬🇧 [English version](../en/05-configuration.md) · [← Retour au README](../../README.fr.md)

Tout se règle dans **`config.yaml`** (copié depuis [`config.example.yaml`](../../config.example.yaml)). Relancez l'application
après modification. Ajouter un lanceur ne demande jamais de toucher au code.

## Sections

| Section | Rôle |
|---|---|
| `language` | `auto` (langue du système), `en`, `fr` |
| `connection` | Nom de la tour, IP Tailscale (`tailscale_ip`), `lan_ip` optionnelle (essayée en second), `user` SSH, `key_file`, `mac`, `connect_timeout` |
| `vars` | Vos propres variables, utilisables en `{{nom}}` dans les commandes (voir plus bas) |
| `health` | `interval_s` (fréquence du contrôle de l'état), `boot_grace_s` (durée « Démarrage » après un WoL) |
| `monitoring` | Télémétrie on/off, `interval_s` ; augmentez-le (ex. 30) sur une connexion limitée, ou `enabled: false` |
| `wake_on_lan` | Adresses de broadcast, ports, unicast optionnel, `relay` SSH |
| `freebox` | WoL Freebox optionnel |
| `files` | `start_path`, `download_dir`, `roots` (raccourcis de l'explorateur) |
| `power` | Commandes lancées par *Redémarrer* / *Éteindre* |
| `local_tools` | Chemins des programmes du **laptop** (Warp, PyCharm, RustDesk), utilisables aussi en `{{warp_exe}}` etc. |
| `actions` | Les cartes de lanceurs |

### Variables

Disponibles partout dans les chaînes : `{{tailscale_ip}}`, `{{lan_ip}}`, `{{user}}`, `{{ssh_port}}`, `{{mac}}`,
`{{project_dir}}`, chaque clé de `local_tools` et de `vars`. Les noms inconnus sont laissés tels quels.

### Mots de passe

La connexion SSH par mot de passe est déconseillée. Si vous y tenez, **ne l'écrivez jamais dans le fichier** : définissez
la variable d'environnement indiquée par `connection.password_env` (`REMOTEHUB_SSH_PASSWORD`).

## Actions

```yaml
actions:
  - id: mon-appli               # unique
    name: "Mon appli"           # titre de la carte       (name_fr: ... pour le français)
    tag: "WEB"                  # petit libellé sur la carte
    category: ai                # dev | ai | system → section d'affichage
    description: "Démarre et ouvre le navigateur"      # (description_fr: ...)
    steps: [ ... ]              # ce que fait le bouton Lancer, dans l'ordre
    stop_steps: [ ... ]         # optionnel : ajoute un bouton Stop
```

Une action peut aussi être une étape unique écrite en ligne (`type: warp_ssh`, `type: local`…).
Les étapes s'exécutent dans l'ordre et s'arrêtent à la première erreur, affichée dans le journal.

### Types d'étapes

| `type` | Paramètres | Effet |
|---|---|---|
| `ssh` | `command` (ligne cmd) **ou** `powershell` (script) · `detach: true` · `ignore_errors: true` · `timeout: 30` | S'exécute sur la **tour**. `detach` le lance en arrière-plan pour qu'il survive à la session SSH |
| `tunnel` | `local_port`, `remote_port`, `remote_host: localhost` | Redirige un port de la tour vers `127.0.0.1:<local_port>` sur le laptop |
| `tunnel_stop` | `local_port` | Ferme un tunnel |
| `wait_port` | `remote_port`, `remote_host`, `timeout`, et un parmi `http_path: /api` (attend une vraie réponse HTTP) · `expect_banner: "SSH-"` · `probe_hex` + `expect_hex` | Attend qu'un service réponde **vraiment** (pas seulement qu'un port s'ouvre) |
| `check_file` | `path` | Échoue tôt, avec un message clair, si un fichier manque sur la tour |
| `url` | `url` | Ouvre une page web ou un schéma personnalisé sur le laptop |
| `local` | `command`, `console: true` | Lance une commande sur le **laptop** |
| `warp_ssh` | `remote_command` (ex. `wsl -d Ubuntu`) ou `command` (commande ssh complète) | Terminal sur la tour : Warp (commande copiée, à coller) → Windows Terminal → cmd |
| `rdp` | `local_port`, `user`, `width`, `height` | Ouvre le Bureau à distance sur un port tunnelisé avec un fichier `.rdp` généré |
| `wait` | `seconds` | Attend |

> **Pourquoi `127.0.0.1` et pas `localhost` dans `remote_host` ?** Windows peut résoudre `localhost` en IPv6 d'abord, ce
> qui ajoute 2 secondes de délai ou cible un service qui n'écoute qu'en IPv4. Préférez `127.0.0.1`.

### Recettes

**Une appli web sur la tour (ex. Streamlit, port 8501), ouverte sur le laptop :**
```yaml
- id: streamlit
  name: "Mon appli Streamlit"
  tag: "WEB"
  category: ai
  description: "streamlit run app.py sur la tour"
  steps:
    - {type: ssh, detach: true, powershell: 'Set-Location C:\work\app; streamlit run app.py --server.address 127.0.0.1 --server.port 8501 --server.headless true'}
    - {type: wait_port, remote_host: "127.0.0.1", remote_port: 8501, http_path: /, timeout: 60}
    - {type: tunnel, local_port: 8501, remote_host: "127.0.0.1", remote_port: 8501}
    - {type: url, url: "http://127.0.0.1:8501"}
  stop_steps:
    - {type: tunnel_stop, local_port: 8501}
    - {type: ssh, ignore_errors: true, powershell: 'Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match "streamlit" } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }'}
```
*Écoutez toujours sur `127.0.0.1`* : le tunnel suffit à le rendre joignable, donc rien n'écoute sur le réseau.

**Un conteneur Docker :**
```yaml
- id: db
  name: "Postgres"
  tag: "DOCKER"
  category: system
  steps:      [{type: ssh, command: "docker start mon-postgres"}]
  stop_steps: [{type: ssh, command: "docker stop mon-postgres"}]
```

**Ouvrir les fichiers de la tour dans VS Code Remote-SSH, PyCharm Gateway, etc. :** ces outils parlent SSH eux-mêmes,
pointez-les vers `votre-utilisateur@<tailscale_ip>`. Une carte peut simplement lancer le programme :
`{type: local, command: '"C:\...\Code.exe"'}`.

**Un tunnel ponctuel sans carte :** utilisez la fenêtre **Tunnels** (un port, ou un lien `http://localhost:3000/chemin`).

## Télémétrie sur une machine particulière

Le script intégré remonte le CPU, la RAM, l'espace libre de `C:` et le GPU NVIDIA (via `nvidia-smi`). Pour autre chose,
renseignez `monitoring.custom_command` avec une commande qui affiche **une ligne JSON** avec certaines de ces clés : `cpu`,
`ram_used_gb`, `ram_total_gb`, `gpu`, `vram_used_mb`, `vram_total_mb`, `gpu_temp`, `disk_c_free_gb`.

## Langues

`language: fr` (ou `en`) force la langue de l'interface. Dans `actions`, ajoutez `name_fr` / `description_fr` (ou
`name_<code>` pour toute langue gérée par l'application) pour traduire le texte des cartes. Ajouter une langue : voir
[CONTRIBUTING](../../CONTRIBUTING.md).

---

**Précédent :** [← 4 · VM Linux](04-vm-linux.md) · **Suite :** [6 · Sécurité →](06-securite.md)

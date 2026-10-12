# 2 · Préparer le laptop (le PC depuis lequel vous travaillez)

> 🇬🇧 [English version](../en/02-laptop-setup.md) · [← Retour au README](../../README.fr.md)

## 1. Prérequis

- Windows 10/11 et [Python 3.10+](https://www.python.org/downloads/) (cochez « Add Python to PATH » à l'installation)
- Le client OpenSSH (déjà dans Windows 10/11 : vérifiez avec `ssh -V`)
- [Tailscale](https://tailscale.com/download), connecté avec le **même compte que la tour**
- Optionnel : [Warp](https://www.warp.dev), [PyCharm](https://www.jetbrains.com/pycharm/), [RustDesk](https://rustdesk.com)

Vérifiez que la tour est joignable : `tailscale ping 100.x.y.z` (l'IP Tailscale de la tour).

## 2. Récupérer RemoteHub-AI

```powershell
git clone https://github.com/anthime24/remotehub-ai.git
cd remotehub-ai
```

(ou téléchargez le ZIP depuis GitHub et décompressez-le).

Envie de regarder avant de configurer ? `python -m venv .venv`, `.venv\Scripts\pip install -r requirements.txt`, puis
`.venv\Scripts\python main.py --demo` ouvre l'interface avec des **données factices** et sans réseau.

## 3. Configurer

Double-cliquez sur **`run.bat`**. Au premier lancement, il copie `config.example.yaml` vers **`config.yaml`** et l'ouvre
dans le Bloc-notes. Modifiez au minimum :

```yaml
connection:
  name: "MA-TOUR"
  tailscale_ip: "100.101.102.103"     # tailscale ip -4   (sur la tour)
  user: "votre-utilisateur-windows"    # le compte donné à Setup-Tower.ps1
  mac: "AA:BB:CC:DD:EE:FF"             # affichée par Setup-Tower.ps1 (ou : ipconfig /all sur la tour)
vars:
  jupyter_token: "<longue chaîne aléatoire>"   # python -c "import secrets;print(secrets.token_urlsafe(32))"
wake_on_lan:
  broadcasts: ["192.168.1.255"]       # adresse de broadcast de votre réseau (x.y.z.255)
```

`config.yaml` est **ignoré par git** : vos adresses et secrets ne quittent jamais votre laptop.
L'application avertit dans son journal si elle trouve encore des valeurs d'exemple. Chaque clé est documentée dans le
fichier et dans [05 · Configuration](05-configuration.md).

Relancez `run.bat`. La première fois, la création de l'environnement virtuel prend une minute.

### Ce que vous devez voir

- En haut à droite : **En ligne · 12 ms** (vert) quand la tour est allumée et joignable via Tailscale.
- La première connexion écrit une ligne jaune *« Première connexion à 100.x.y.z : clé d'hôte SHA256:… mémorisée »*. La clé
  est enregistrée dans `~/.ssh/known_hosts`. Pour être strict, comparez l'empreinte avec
  `ssh-keygen -lf C:\ProgramData\ssh\ssh_host_ed25519_key.pub` lancé sur la tour. **Si cette clé change un jour,
  RemoteHub refuse de se connecter** et explique pourquoi (voir [Sécurité](06-securite.md)).
- Les barres CPU / RAM / GPU en direct à droite.

## 4. Déployer les scripts de la tour

Les lanceurs de services (Ollama, ComfyUI, JupyterLab) et le script de VM vivent sur la tour. Copiez-les avec :

```powershell
python tools\deploy_tower.py --dry-run      # liste ce qui sera copié
python tools\deploy_tower.py                # copie tower\services et tower\vm vers vars.scripts_dir (défaut C:\RemoteHub)
```

L'outil utilise votre session SSH : pas de mot de passe en plus, rien d'autre à configurer. Relancez-le après une mise à jour.

## 5. Utilisation au quotidien

| Vous voulez… | Faites ceci |
|---|---|
| Allumer la tour | **Réveiller la tour** (même réseau local ; de l'extérieur voir [Wake-on-LAN](03-wake-on-lan.md)) |
| Ouvrir un terminal dessus | Carte **Terminal (SSH)** (Warp : collez avec Ctrl+V ; repli sur Windows Terminal) |
| Utiliser Ollama depuis le laptop | Carte **Ollama**, puis `http://127.0.0.1:11435` comme URL Ollama dans vos outils |
| Ouvrir une appli web qui tourne sur la tour | **Tunnels** → saisissez `3000` ou `http://localhost:3000` |
| Naviguer avec le réseau de la tour | **Tunnels** → *Navigateur via la tour* |
| Copier des fichiers | **Fichiers** (parcourir, chercher, envoyer des dossiers, télécharger) |
| Travailler sur un bureau Linux | Carte **Bureau Linux (RDP)** ([guide VM](04-vm-linux.md)) |
| L'éteindre | **Éteindre** (fenêtre de confirmation) |

Tout ce qui est lancé depuis les cartes s'exécute **sur la tour**, détaché de votre session SSH : fermer l'application
n'arrête pas votre notebook ni votre serveur de modèles. Utilisez le bouton **Stop** de chaque carte quand vous avez fini.

## 6. Mettre à jour

```powershell
git pull
.venv\Scripts\pip install -r requirements.txt
python tools\deploy_tower.py
```

Comparez `config.example.yaml` avec votre `config.yaml` après une mise à jour pour reprendre les nouvelles options.

---

**Précédent :** [← 1 · Tour](01-installation-tour.md) · **Suite :** [3 · Wake-on-LAN →](03-wake-on-lan.md)

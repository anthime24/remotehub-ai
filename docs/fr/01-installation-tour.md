# 1 · Préparer la tour (le PC que vous voulez contrôler)

> 🇬🇧 [English version](../en/01-tower-setup.md) · [← Retour au README](../../README.fr.md)

La **tour** est le PC Windows (fixe ou portable) qui fait le gros du travail. Ce guide prend environ 20 minutes.
Rien ici n'ouvre de port sur Internet.

**Il vous faut :** Windows 10/11 (la version Famille convient), un compte administrateur, un câble Ethernet si vous
voulez le Wake-on-LAN, et un compte [Tailscale](https://tailscale.com) gratuit.

---

## Étape 1 — Installer Tailscale sur la tour

Tailscale crée un réseau privé chiffré entre *vos* appareils, même derrière une box ou en 4G.

1. Téléchargez-le sur <https://tailscale.com/download> et connectez-vous.
2. Dans un terminal, notez l'adresse de la tour :
   ```powershell
   tailscale ip -4        # affiche par exemple 100.101.102.103
   ```
3. Faites la même chose sur le laptop **avec le même compte** (voir [l'étape 2 du guide laptop](02-installation-laptop.md)).

> Astuce : dans la console d'administration Tailscale, donnez un nom clair à la tour et désactivez l'expiration de clé
> pour elle si vous voulez qu'elle reste joignable des mois sans reconnexion (vous pouvez la garder pour le laptop).

## Étape 2 — Récupérer les scripts sur la tour

Sur la tour, téléchargez ce dépôt (**Code → Download ZIP**, puis décompressez) ou faites un `git clone`.
Seul le dossier `tower\` est nécessaire.

## Étape 3 — Créer votre clé SSH sur le laptop

Sur le **laptop**, dans PowerShell :

```powershell
ssh-keygen -t ed25519 -C "remotehub laptop"
# Entrée pour l'emplacement par défaut, puis CHOISISSEZ UNE PHRASE DE PASSE.
type $HOME\.ssh\id_ed25519.pub
```

La dernière commande affiche une ligne qui commence par `ssh-ed25519 AAAA…` : c'est votre clé **publique**, vous pouvez
la partager. Copiez-la vers la tour (clé USB, message à vous-même…). Ne copiez **jamais** le fichier sans `.pub` : c'est
votre clé privée, elle reste sur le laptop.

## Étape 4 — Lancer le script d'installation (PowerShell administrateur sur la tour)

Clic droit sur le bouton Démarrer → **Terminal (admin)**, puis :

```powershell
cd chemin\vers\remotehub-ai\tower

# 1) Aperçu : montre ce qui changerait, ne change rien
powershell -ExecutionPolicy Bypass -File .\Setup-Tower.ps1 -DryRun

# 2) Application, en installant votre clé publique (collez le texte de la clé, ou le chemin du fichier .pub)
powershell -ExecutionPolicy Bypass -File .\Setup-Tower.ps1 -PublicKey "ssh-ed25519 AAAA… remotehub laptop"
```

Ce qu'il fait (chaque étape est idempotente : relancez-le quand vous voulez) :

| Étape | Effet |
|---|---|
| Serveur OpenSSH | Installe la fonctionnalité Windows, démarre `sshd` automatiquement au boot |
| Clé publique | Ajoute votre clé à `administrators_authorized_keys` (comptes admin) ou `~\.ssh\authorized_keys`, avec des droits restreints |
| `sshd_config` | Ajoute un bloc balisé (`# BEGIN RemoteHub … # END RemoteHub`) : 3 tentatives de connexion, clé activée, redirection TCP activée. **Une sauvegarde est faite avant** et le fichier est validé par `sshd -t` ; en cas d'erreur la sauvegarde est restaurée |
| Pare-feu | Signale les règles qui autorisent SSH depuis n'importe quelle adresse ; avec `-RestrictFirewall`, limite SSH à Tailscale |
| Wake-on-LAN | Active le réveil par paquet magique sur la carte Ethernet, coupe les économies d'énergie qui le cassent, désactive le démarrage rapide |

Il se termine en affichant les valeurs à mettre dans le `config.yaml` du laptop (nom, IP Tailscale, adresse MAC, IP LAN).

Options : `-User <nom>` (compte SSH, par défaut l'utilisateur courant), `-WolAdapter "Ethernet"` (choisir la carte),
`-LanSubnet 192.168.1.0/24` (autoriser aussi votre réseau local quand le pare-feu est restreint).

## Étape 5 — Tester la connexion par clé, **puis** verrouiller

Depuis le laptop :

```powershell
ssh votre-utilisateur-windows@100.x.y.z hostname
```

Vous devez obtenir le nom de la tour après avoir saisi la phrase de passe de votre clé (sans demande de mot de passe
Windows). Quand cela marche :

```powershell
# sur la tour, en administrateur :
powershell -ExecutionPolicy Bypass -File .\Setup-Tower.ps1 -RestrictFirewall -DisablePasswordAuth
```

- `-RestrictFirewall` → SSH joignable **uniquement** depuis Tailscale (`100.64.0.0/10`) [+ votre LAN avec `-LanSubnet`].
  Les autres règles entrantes qui autorisaient le port 22 sont désactivées et listées dans `C:\ProgramData\RemoteHub\`
  pour pouvoir annuler.
- `-DisablePasswordAuth` → connexion par clé uniquement. Le script refuse si aucune clé n'est installée : impossible
  de vous enfermer dehors par accident.

## Étape 6 — Réglages BIOS pour le Wake-on-LAN

Lisez [Wake-on-LAN](03-wake-on-lan.md) : une option du BIOS (« Power On By PCI-E » / « Wake on LAN ») doit être activée.

## Étape 7 — Logiciels optionnels

N'installez que ce que vous utiliserez. RemoteHub les démarre et les arrête pour vous :

| Fonction | À installer sur la tour |
|---|---|
| Modèles d'IA | [Ollama](https://ollama.com/download) |
| Génération d'images | [ComfyUI](https://github.com/comfyanonymous/ComfyUI) (variable `COMFYUI_DIR`, ou `C:\Users\vous\ComfyUI`) |
| Notebooks | `pip install jupyterlab` |
| Bureau à distance | [RustDesk](https://rustdesk.com) → Paramètres → Sécurité → **Activer l'accès direct par IP**, mot de passe permanent |
| VM Linux | [VirtualBox](https://www.virtualbox.org/) → [guide](04-vm-linux.md) |
| Shell Linux | `wsl --install -d Ubuntu` |
| Conteneurs | Docker Desktop |

Déployez ensuite les scripts d'aide depuis le laptop (voir le [guide laptop](02-installation-laptop.md#4-déployer-les-scripts-de-la-tour)).

---

**Suite :** [2 · Préparer le laptop →](02-installation-laptop.md)

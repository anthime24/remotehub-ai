# 4 · Une vraie machine Linux sur la tour (VirtualBox)

> 🇬🇧 [English version](../en/04-linux-vm.md) · [← Retour au README](../../README.fr.md)

Obtenez un **Ubuntu** complet (terminal et bureau graphique) qui tourne sur le CPU/la RAM de la tour, démarré et arrêté
depuis RemoteHub.

**Pourquoi VirtualBox et pas Hyper-V ?** Hyper-V n'existe pas dans Windows *Famille*, et sur certaines installations Pro
son magasin de composants est abîmé. VirtualBox fonctionne partout (il utilise automatiquement la Windows Hypervisor
Platform si elle est activée : le moteur « NEM »). Si vous n'avez besoin que d'un shell Linux, **WSL2** est plus léger :
utilisez la carte `Terminal Ubuntu (WSL2)` et passez cette page.

```
laptop ──session SSH (Tailscale)──▶ tour ──127.0.0.1:2223──▶ sshd de la VM   (NAT VirtualBox)
                                          └─127.0.0.1:33890─▶ xrdp de la VM   (bureau à distance)
```

La VM est derrière le NAT de VirtualBox et ses ports sont redirigés vers **127.0.0.1 de la tour uniquement**. Personne,
sur aucun réseau, ne peut les atteindre ; RemoteHub les ouvre *à l'intérieur* du tunnel SSH.

## 1. Installer VirtualBox et récupérer une ISO Ubuntu (sur la tour)

```powershell
winget install Oracle.VirtualBox
```

Téléchargez **Ubuntu Server 24.04 LTS** (ISO « live server », ~2,6 Go) sur <https://ubuntu.com/download/server> et vérifiez
son SHA-256 avec le fichier `SHA256SUMS` du même site :

```powershell
(Get-FileHash .\ubuntu-24.04.*-live-server-amd64.iso -Algorithm SHA256).Hash
```

## 2. Créer la VM

PowerShell administrateur sur la tour, dans le dossier `tower\vm` :

```powershell
powershell -ExecutionPolicy Bypass -File .\Create-LinuxVm.ps1 `
    -IsoPath D:\VM\ubuntu-24.04.5-live-server-amd64.iso -WithDesktop -Locale fr_FR -Country FR -TimeZone Europe/Paris
```

Le mot de passe de l'utilisateur Linux vous est demandé (8 caractères minimum ; il n'est écrit ni dans un journal ni dans
la ligne de commande). Valeurs par défaut : 4 Go de RAM, 2 vCPU, disque dynamique de 40 Go, utilisateur `remotehub`,
ports 2223 (SSH) et 33890 (RDP). Modifiables : `-MemoryMB 6144 -Cpus 4 -DiskGB 60 -User alice -VmName MaVM -SshPort … -RdpPort …`.
`-WithDesktop` installe aussi le bureau XFCE et `xrdp`.

Le script refuse de s'exécuter si le nom de la VM ou un port est déjà pris : il n'écrase jamais rien.
L'installation automatique dure **10 à 25 minutes**, sans fenêtre. Suivez-la avec :

```powershell
powershell -ExecutionPolicy Bypass -File .\ensure_vm.ps1     # renvoie 0 quand le SSH de la VM répond
Get-Content $env:ProgramData\RemoteHub\logs\vm-create.log
```

Faites correspondre `vars.vm_name` / `vars.vm_user` dans le `config.yaml` du laptop, puis lancez
`python tools\deploy_tower.py` (il copie `ensure_vm.ps1` dans le `scripts_dir` de la tour).

## 3. Première connexion et clé SSH

1. Dans RemoteHub, cliquez **Lancer** sur **Terminal VM Linux**. Le terminal ouvre une session SSH vers la VM :
   connectez-vous une première fois avec le mot de passe choisi.
2. Installez la clé publique du laptop *dans la VM* et coupez le mot de passe pour SSH :
   ```bash
   mkdir -p ~/.ssh && chmod 700 ~/.ssh
   echo "ssh-ed25519 AAAA… remotehub laptop" >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys
   # puis, depuis le laptop, vérifiez que la clé fonctionne (nouveau terminal) AVANT la commande suivante :
   printf 'PasswordAuthentication no\nPermitRootLogin no\n' | sudo tee /etc/ssh/sshd_config.d/99-remotehub.conf
   sudo systemctl reload ssh
   ```
   (La VM n'est joignable que par votre tunnel : c'est de la défense en profondeur, mais ça ne coûte rien.)

> **Si SSH ne répond jamais** (l'installation semble finie mais le port 2223 reste muet) : l'étape d'installation des
> paquets a pu échouer. Accédez au bureau de la tour (RustDesk), ouvrez la fenêtre de la VM dans VirtualBox, connectez-vous
> et lancez `sudo apt update && sudo apt install -y openssh-server` (et `xfce4 xrdp xorgxrdp` pour le bureau). Puis, avec
> votre utilisateur : `echo xfce4-session > ~/.xsession`.

## 4. Le bureau graphique

Cliquez **Lancer** sur **Bureau Linux (RDP)** : RemoteHub démarre la VM si besoin, attend que `xrdp` réponde *vraiment*,
ouvre un tunnel et lance le Bureau à distance de Windows avec un fichier `.rdp` généré. Connectez-vous avec l'utilisateur et
le mot de passe de la VM (type de session *Xorg*). Si le bureau reste noir, vérifiez que `~/.xsession` contient `xfce4-session`.

### Le rendre plus joli / ressembler à Ubuntu

```bash
sudo apt install -y yaru-theme-gtk yaru-theme-icon fonts-ubuntu ubuntu-wallpapers plank \
                    arc-theme papirus-icon-theme
```
Puis *Paramètres → Apparence* : choisissez *Yaru-dark* (ou *Arc-Dark* + icônes *Papirus-Dark*) et le fond d'écran.
Ajoutez `plank` dans *Session et démarrage → Démarrage automatique* pour un dock façon Ubuntu.
Envie du bureau GNOME complet ? `sudo apt install ubuntu-desktop-minimal` fonctionne mais est lourd en RDP.

## 5. Au quotidien

| Carte | Ce qu'elle fait |
|---|---|
| **VM Linux (Ubuntu)** — Lancer | Démarre la VM et attend SSH. **Stop** = extinction ACPI propre |
| **Terminal VM Linux** | Démarre si besoin, ouvre le tunnel, ouvre un terminal SSH |
| **Bureau Linux (RDP)** | Démarre si besoin, ouvre le tunnel, ouvre le bureau graphique |

`ensure_vm.ps1` fiabilise le démarrage : il ne *réinitialise* qu'une VM qu'**il** a démarrée et qui s'est figée au boot
(un défaut connu de VirtualBox en mode NEM, 3 essais maximum). Une VM déjà en marche quand vous cliquez n'est **jamais**
redémarrée.

## 6. Sauvegardes, instantanés, ressources

- Instantané avant un changement risqué : `& "C:\Program Files\Oracle\VirtualBox\VBoxManage.exe" snapshot MaVM take avant-mise-a-jour`
- Changer RAM/CPU, VM éteinte : `VBoxManage modifyvm MaVM --memory 6144 --cpus 4`
- Le disque est dynamique (il grossit à l'usage) : surveillez l'espace libre de la tour.
- Tout supprimer : `VBoxManage unregistervm MaVM --delete`

---

**Précédent :** [← 3 · Wake-on-LAN](03-wake-on-lan.md) · **Suite :** [5 · Configuration →](05-configuration.md)

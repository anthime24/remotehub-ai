# 7 · Dépannage

> 🇬🇧 [English version](../en/07-troubleshooting.md) · [← Retour au README](../../README.fr.md)

Commencez par le panneau **Journal** en bas de la fenêtre : les messages sont colorés (vert OK, jaune avertissement, rouge erreur).

## Le badge indique **Hors ligne**

| Vérification | Comment |
|---|---|
| La tour est-elle allumée et réveillée ? | Regardez-la / utilisez **Réveiller la tour** et attendez jusqu'à 4 minutes |
| Tailscale est-il connecté sur **les deux** machines ? | `tailscale status` : la tour doit apparaître active, pas « offline » |
| Le laptop l'atteint-il ? | `tailscale ping 100.x.y.z` puis `Test-NetConnection 100.x.y.z -Port 22` |
| Bonne IP dans `config.yaml` ? | `tailscale ip -4` sur la tour |
| Pare-feu ? | Si vous avez lancé `-RestrictFirewall`, la règle n'autorise que Tailscale (et `-LanSubnet`). Voir `Get-NetFirewallRule -DisplayName "RemoteHub SSH"` |
| sshd tourne-t-il ? | Sur la tour : `Get-Service sshd` |

## Le badge est jaune : « SSH en cours de connexion… » (port ouvert, pas de login)

- **« Authentification SSH refusée »** dans le journal → votre clé publique n'est pas installée, ou ses droits sont faux.
  Sur la tour : pour un compte administrateur, la clé doit être dans `C:\ProgramData\ssh\administrators_authorized_keys`
  (pas dans `~\.ssh`), lisible uniquement par *Administrateurs* et *SYSTEM*. Relancez `Setup-Tower.ps1 -PublicKey …`.
  Testez avec `ssh -v votre-utilisateur@100.x.y.z` et lisez les dernières lignes.
- **Clé avec phrase de passe que RemoteHub n'arrive pas à utiliser ?** Chargez-la dans `ssh-agent` (`ssh-add`) : RemoteHub utilise l'agent.
- **« CLÉ D'HÔTE MODIFIÉE »** → la tour a été réinstallée (nouvelles clés d'hôte) *ou* quelqu'un l'usurpe. Si vous avez
  réinstallé Windows/OpenSSH, supprimez la ligne de la tour dans `C:\Users\vous\.ssh\known_hosts` et reconnectez-vous.

## Des boutons échouent

- *« fichier introuvable sur la tour : …\Start-Ollama.ps1 »* → lancez `python tools\deploy_tower.py` ; vérifiez `vars.scripts_dir`.
- *« le service du port 8188 n'a pas répondu en 180 s »* → le programme n'a pas démarré. Les journaux sont dans
  `C:\ProgramData\RemoteHub\logs\` sur la tour (`comfyui.err.log`, `ollama.err.log`, `jupyter.err.log`).
- *« Port local 11435 indisponible »* → un autre programme l'utilise ; changez `local_port` dans l'action (et l'URL que vous utilisez).
- *Ollama ne trouve pas le modèle* → les modèles sont propres à chaque machine : `ollama pull <modèle>` **sur la tour** (ou via le tunnel de la carte Ollama, `OLLAMA_HOST=http://127.0.0.1:11435 ollama pull <modèle>`).
- *JupyterLab : « Refusing to start … weak token »* → renseignez un `vars.jupyter_token` de 16 caractères ou plus.
- *Warp s'ouvre mais rien ne se lance* → voulu sous Windows : la commande est dans le presse-papiers, faites **Ctrl+V** puis **Entrée**.
- Une étape reste longtemps sur « Attente de … » → le service met du temps à démarrer (premier lancement de ComfyUI, gros modèle). Elle s'arrête au `timeout` de l'étape.

## Le Wake-on-LAN ne fait rien

Lisez [Wake-on-LAN §4](03-wake-on-lan.md#4-dépannage-du-wol). Tests rapides : (1) réveillez-la depuis un autre PC du même LAN ;
(2) vérifiez `connection.mac` et `wake_on_lan.broadcasts` ; (3) hors du LAN il faut un relais ou l'option Freebox.

## La VM Linux

| Symptôme | Solution |
|---|---|
| Reste sur « Attente de service prêt… » | La VM peut se figer au boot en mode NEM. `ensure_vm.ps1` la réinitialise jusqu'à 3 fois ; voir `C:\ProgramData\RemoteHub\logs\vm-ensure.log` |
| RDP : « échec de connexion » | Mauvais mot de passe pour l'utilisateur *Linux* (pas celui de Windows). Réinitialisez dans un terminal de la VM : `sudo passwd <utilisateur>` |
| RDP : écran noir / déconnexion immédiate | Dans la VM : `echo xfce4-session > ~/.xsession`, puis `sudo systemctl restart xrdp` ; vérifiez qu'une autre session RDP n'est pas déjà ouverte |
| `Create-LinuxVm.ps1` : « port déjà utilisé » | Choisissez d'autres ports avec `-SshPort` / `-RdpPort` (et mettez à jour les ports de l'action) |
| « VT-x non disponible » | Activez la virtualisation (SVM/VT-x) dans le BIOS |

## Fichiers

- Transferts lents en 4G/Tailscale relayé → normal ; la barre de progression affiche la vitesse et le temps restant. **Annuler** est immédiat.
- *« Accès refusé »* sur un dossier → le compte SSH n'a pas les droits à cet endroit.

## Particularités d'OpenSSH sous Windows (bon à savoir)

- L'ouverture d'un port redirigé **réussit toujours** avec OpenSSH de Windows, même si rien n'écoute sur la cible ;
  RemoteHub lit donc la connexion pour détecter un port « vraiment ouvert ». Si un onglet de navigateur s'ouvre vide, le service
  derrière le tunnel est arrêté.
- Les processus lancés dans une session SSH meurent avec elle. Les cartes utilisent WMI (`detach`) pour démarrer les
  services de longue durée en dehors de la session.

## Réseaux qui bloquent Tailscale

Dans certaines écoles, universités et entreprises, le pare-feu bloque le trafic VPN, Tailscale compris. Symptômes :
`tailscale status` montre la tour hors ligne/relayée sans données reçues, `tailscale netcheck` n'affiche ni UDP ni DERP
joignable, et RemoteHub reste **Hors ligne**.

- RemoteHub-AI ne contient **aucune astuce** pour déjouer ces filtres. C'est la décision du propriétaire du réseau et les
  contourner peut enfreindre le règlement que vous avez accepté.
- Ce qui fonctionne : **demander à l'équipe informatique** d'autoriser Tailscale (un message court et poli expliquant votre
  usage), ou passer par le **partage de connexion de votre téléphone** (votre propre réseau). Sur un partage de connexion,
  économisez les données : baissez la télémétrie (`monitoring.interval_s: 30`), évitez RDP et RustDesk, privilégiez le
  terminal, Fichiers et les tunnels d'API.
- Alternative sans connexion en direct : poussez votre travail avec Git et laissez la tour l'exécuter plus tard.

## Toujours bloqué ?

Ouvrez une [issue](https://github.com/OWNER/remotehub-ai/issues) avec : ce que vous avez fait, ce que vous attendiez, ce qui
s'est passé, les lignes du journal (secrets retirés), vos versions de Windows. **Ne collez jamais votre clé, jeton, IP
Tailscale ou adresse MAC.**

---

**Précédent :** [← 6 · Sécurité](06-securite.md) · [Retour au README](../../README.fr.md)

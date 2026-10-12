# 3 · Wake-on-LAN

> 🇬🇧 [English version](../en/03-wake-on-lan.md) · [← Retour au README](../../README.fr.md)

Le Wake-on-LAN (WoL) allume la tour en lui envoyant un **paquet magique** (6 octets `FF` suivis 16 fois de son adresse
MAC), que sa carte réseau écoute même quand le PC est éteint.

> **La vérité à connaître :** ce paquet est un *broadcast* du réseau local. Il ne traverse pas Internet. Depuis
> l'extérieur (4G, école, Wi-Fi d'un ami), quelque chose **à l'intérieur du LAN** doit l'envoyer pour vous. C'est
> le rôle du « relais » et de l'option « Freebox » ci-dessous.

## 1. Rendre la tour réveillable

1. **BIOS/UEFI** (indispensable, Windows ne peut pas le faire) : activez **Wake on LAN** / **Power On By PCI-E**
   (le nom varie : *Wake on PCIE/PCI*, *Resume by LAN*…) et **désactivez** *ErP Ready*, *EuP*, *Deep Sleep* : avec
   ceux-ci actifs, la carte réseau n'est plus alimentée à l'arrêt (les LED de la prise RJ45 s'éteignent).
2. **Windows** : `Setup-Tower.ps1` active le réveil par paquet magique sur la carte Ethernet, coupe Green Ethernet / EEE et
   désactive le démarrage rapide. Vérification manuelle : Gestionnaire de périphériques → carte Ethernet → *Gestion de
   l'alimentation* : « Autoriser ce périphérique à sortir l'ordinateur de veille » + « Autoriser uniquement un paquet magique ».
3. **Filaire uniquement.** Les cartes Wi-Fi gèrent rarement le WoL depuis un arrêt complet. Utilisez Ethernet.
4. **Réservez l'IP LAN de la tour** dans votre box (bail DHCP statique) : `lan_ip` et l'adresse de broadcast restent stables.

Trouver l'adresse MAC : `ipconfig /all` sur la tour → « Adresse physique » de la carte Ethernet (`AA-BB-CC-DD-EE-FF`).
Mettez-la dans `connection.mac`.

## 2. Même réseau : le bouton **Réveiller** suffit

RemoteHub envoie le paquet magique sur **chaque interface réseau du laptop** (Wi-Fi, Ethernet, cartes virtuelles) vers
chaque adresse de `wake_on_lan.broadcasts`, sur les ports 9 et 7. Réglez le broadcast sur votre réseau :

```yaml
wake_on_lan:
  broadcasts: ["192.168.1.255", "255.255.255.255"]
```

(Un réseau `192.168.1.0/24` a pour broadcast `192.168.1.255`.) Après l'envoi, le badge passe au jaune (« Démarrage… »)
pendant `health.boot_grace_s` secondes, puis au vert quand SSH répond.

## 3. Depuis l'extérieur du LAN

### Option A : un relais (fonctionne avec n'importe quelle box)

Un appareil toujours allumé du LAN et joignable via Tailscale (Raspberry Pi, NAS, mini-PC) envoie le paquet pour vous.

Sur le relais (Linux) : installez Tailscale, puis `sudo apt install wakeonlan`. Dans `config.yaml` :

```yaml
wake_on_lan:
  relay:
    enabled: true
    host: "100.x.y.z"          # l'IP Tailscale du relais
    user: "pi"
    key_file: "~/.ssh/id_ed25519"
    command: "wakeonlan {{mac}}"
```

Faites `ssh pi@100.x.y.z` une fois pour que la clé d'hôte du relais soit dans `~/.ssh/known_hosts` (RemoteHub refuse
les relais inconnus).

### Option B : le WoL de la box (Freebox, France)

La Freebox peut envoyer le paquet depuis l'intérieur du LAN via son API, même quand vous êtes en 4G.

1. Freebox OS → *Paramètres de la Freebox → Mode avancé → Accès distant* : activez **l'accès distant HTTPS**.
2. À la maison : `python tools\register_freebox.py` puis appuyez sur **✔ / la flèche droite** de l'écran de la Freebox Server.
3. Freebox OS → *Gestion des accès → Applications* → RemoteHub-AI : cochez **« Modification des réglages de la Freebox »**.
4. Mettez `freebox.enabled: true`.

Le jeton est stocké dans `freebox_token.json` (ignoré par git, à traiter comme un mot de passe).
Autres box : beaucoup de routeurs (OpenWrt, pfSense, UniFi, Mikrotik…) savent envoyer du WoL : utilisez l'option A, ou
proposez une PR avec un nouveau fournisseur !

## 4. Dépannage du WoL

- **Testez d'abord depuis le LAN de la tour**, avec un autre PC : si ça échoue, le problème vient du BIOS/Windows, pas de RemoteHub.
- **Ça marche juste après un arrêt mais pas après une coupure de courant / une longue extinction ?** La carte a perdu
  l'alimentation de veille : vérifiez le BIOS, l'interrupteur du bloc d'alimentation et ErP.
- **Répéteurs Wi-Fi / CPL** : ils réécrivent parfois les adresses MAC (MAC-NAT). Un *broadcast* les traverse quand même
  (la MAC cible est dans la charge utile du paquet), mais pas un *unicast* vers l'IP de la tour. C'est pourquoi le
  broadcast est le mode par défaut.
- **ARP :** les box oublient l'association IP↔MAC quelques minutes après l'extinction : l'unicast (`wake_on_lan.unicast`) est peu fiable.
- Le démarrage rapide de Windows est une hibernation déguisée : `Setup-Tower.ps1` le désactive.

---

**Précédent :** [← 2 · Laptop](02-installation-laptop.md) · **Suite :** [4 · VM Linux →](04-vm-linux.md)

# 6 · Sécurité

> 🇬🇧 [English version](../en/06-security.md) · [← Retour au README](../../README.fr.md) · [Politique de sécurité](../../SECURITY.md)

Contrôler un PC à distance n'a d'intérêt que si c'est sûr. Cette page explique **comment** RemoteHub-AI est conçu pour
l'être, quels risques restent, et ce que vous devez faire.

## Le principe en un schéma

```
Internet ──✗── (aucun port redirigé, aucune DMZ, rien n'écoute pour le public)

laptop ═══ Tailscale (WireGuard, chiffré, authentifié par appareil) ═══ tour :22 (sshd, connexion par clé)
   │                                                                      │
   └── UNE session SSH transporte tout le reste :                         ├─ 127.0.0.1:11434  Ollama
         tunnels, SOCKS5, SFTP, commandes                                 ├─ 127.0.0.1:8888   JupyterLab (+ jeton)
                                                                          ├─ 127.0.0.1:8188   ComfyUI
                                                                          ├─ 127.0.0.1:21118  RustDesk (IP directe)
                                                                          └─ 127.0.0.1:2223/33890  VM (NAT VirtualBox)
```

1. **Aucune exposition publique.** Vous ne redirigez aucun port sur votre box. Tailscale connecte les appareils en sortie.
2. **Une seule porte.** Seul SSH (port 22) est joignable, et seulement depuis Tailscale (et éventuellement votre LAN) après
   `Setup-Tower.ps1 -RestrictFirewall`.
3. **Tout le reste est en loopback.** Ollama, Jupyter, ComfyUI, RustDesk et la VM écoutent sur `127.0.0.1` et sont atteints
   par redirection de ports SSH. Les scripts de services de ce dépôt écoutent sur `127.0.0.1` volontairement.
4. **Des clés, pas des mots de passe.** Connexion SSH par clé ; le mot de passe peut être coupé (`-DisablePasswordAuth`).
5. **Clé d'hôte épinglée.** Première connexion → clé mémorisée dans `~/.ssh/known_hosts`. Si elle change, RemoteHub
   **refuse** avec un message explicite au lieu de se reconnecter en silence. (C'est ce qui empêche quelqu'un sur le même
   réseau de se faire passer pour votre tour.)
6. **Les secrets restent chez vous.** `config.yaml`, `freebox_token.json`, `.privacy-denylist` sont ignorés par git. Le mot de
   passe SSH n'est lu que dans une variable d'environnement. Jupyter exige un jeton que le script de service **refuse de
   démarrer sans** (pas de `change-me`, 16 caractères minimum).
7. **Transferts de fichiers sûrs.** Les téléchargements vont dans `nom.part` renommé à la fin (jamais de fichier tronqué
   sous le vrai nom) ; les envois sont vérifiés en taille et un envoi raté est supprimé de la tour ; les écrasements
   demandent confirmation.

## Risques résiduels : soyons honnêtes

| Risque | Pourquoi c'est important | Que faire |
|---|---|---|
| **Votre clé privée = les clés de la tour** | Le compte SSH est généralement administrateur | Phrase de passe, `ssh-agent`, chiffrement du disque (BitLocker) sur le laptop. Ne copiez jamais la clé privée |
| **Laptop volé/compromis** | Il contient la clé et une session Tailscale | Retirez la clé de la tour (`C:\ProgramData\ssh\administrators_authorized_keys`) et supprimez l'appareil dans la console Tailscale |
| **Compte Tailscale piraté** | Celui qui le contrôle peut ajouter des appareils à votre réseau | Double authentification chez le fournisseur d'identité, *approbation des appareils*, revue régulière des appareils |
| **Autres appareils de votre tailnet** | Ils peuvent atteindre le port 22 | Utilisez les **ACL** Tailscale (ci-dessous) pour que seul votre laptop atteigne la tour sur le port 22 |
| **Un processus de la tour lisant `127.0.0.1`** | Les services en loopback sont visibles des utilisateurs/processus locaux | Jeton Jupyter (fait) ; n'exécutez pas de logiciel douteux sur la tour ; gardez Windows à jour |
| **Une session SSH administrateur est puissante par nature** | RemoteHub peut lancer toute commande que vous configurez | N'ajoutez que des actions que vous comprenez ; traitez un `config.yaml` partagé comme du code |
| **Navigateur via la tour (SOCKS)** | Le navigateur dédié atteint votre LAN domestique (box, NAS…) | C'est la fonction : ne l'utilisez que sur des sites de confiance, fermez le proxy ensuite |

### Exemple d'ACL Tailscale (console d'admin → Access controls)

Seul le laptop atteint le port SSH de la tour ; la tour ne peut pas initier de connexion vers le laptop :

```json
{
  "tagOwners": { "tag:tower": ["autogroup:admin"] },
  "acls": [
    { "action": "accept", "src": ["autogroup:member"], "dst": ["tag:tower:22"] }
  ]
}
```
Étiquetez la tour (`tag:tower`) dans la liste des machines. Adaptez `src` à un utilisateur ou un appareil précis si vous
partagez le tailnet.

## Liste de durcissement

- [ ] Clé avec phrase de passe ; clé chargée dans `ssh-agent` (`Get-Service ssh-agent | Set-Service -StartupType Manual; Start-Service ssh-agent; ssh-add`)
- [ ] `Setup-Tower.ps1 -RestrictFirewall` et `-DisablePasswordAuth` appliqués
- [ ] Tailscale : 2FA, ACL, expiration de clé sur le laptop, approbation des appareils
- [ ] `vars.jupyter_token` long et aléatoire ; mot de passe permanent RustDesk long et aléatoire
- [ ] Aucune redirection de port vers la tour, aucune DMZ, aucun port ouvert par UPnP (vérifiez la page de votre box)
- [ ] BitLocker/chiffrement de l'appareil sur le laptop ; verrouillage d'écran
- [ ] Windows Update, Tailscale, OpenSSH et VirtualBox à jour

## Publier votre propre fork en sécurité

Votre configuration contient des valeurs privées (IP Tailscale, MAC, nom d'utilisateur, jetons). Ce dépôt est construit
pour qu'elles ne soient jamais commitées, mais **vous** devez le garder ainsi :

```powershell
git config core.hooksPath .githooks        # hook de pré-commit
python tools\check_privacy.py              # analyse immédiate
```

Le contrôleur cherche les clés privées, jetons, adresses Tailscale (100.64.0.0/10), adresses MAC, e-mails, chemins de profil
Windows, et chaque ligne de **`.privacy-denylist`**, un fichier ignoré par git où vous listez vos propres chaînes privées
(IP, MAC, noms d'utilisateur et d'ordinateur, domaines, e-mail), une par ligne. La CI applique les motifs génériques à
chaque push. Captures d'écran : utilisez `python main.py --demo` (données factices), jamais une capture de votre vraie fenêtre.

Si un secret a été commité par erreur, **révoquez-le d'abord** (nouvelle clé, nouveau jeton), puis réécrivez l'historique :
supprimer le fichier dans un commit suivant ne suffit pas, il reste dans l'historique.

## Réseaux qui bloquent Tailscale (écoles, entreprises)

Certains réseaux bloquent le trafic VPN/Tailscale. RemoteHub-AI ne propose volontairement **aucun contournement** des
filtres qu'une organisation a choisi d'appliquer : les contourner peut enfreindre le règlement du réseau et vous causer des
ennuis. Demandez à l'équipe informatique (elle peut autoriser Tailscale : une demande courte et polie expliquant votre
usage fonctionne le mieux), ou utilisez le partage de connexion de votre téléphone (voir le
[dépannage](07-depannage.md#réseaux-qui-bloquent-tailscale)).

---

**Précédent :** [← 5 · Configuration](05-configuration.md) · **Suite :** [7 · Dépannage →](07-depannage.md)

# Tristan HOME

Intégrations personnalisées pour mon usage personnel

## Automatisation : être notifié d'un pipi/caca

À chaque passage concluant (durée ≥ seuil pipi), l'intégration Fuji émet un
événement `fuji_visit_completed` avec les données suivantes :

| Champ | Exemple | Description |
|---|---|---|
| `device_id` | `abc123...` | `entry_id` de l'intégration Fuji concernée. |
| `type` | `pipi` ou `caca` | Type de passage (en minuscules, contrairement à l'état du capteur `sensor...dernier_passage` qui affiche `Pipi`/`Caca`). |
| `duration_seconds` | `25` | Durée du passage, en secondes. |
| `started_at` / `ended_at` | ISO 8601 | Horodatage de début/fin du passage. |

C'est le déclencheur le plus fiable (il ne se déclenche qu'une fois par
passage réellement validé, contrairement à un trigger sur l'état qui peut
se redéclencher inutilement).

### Exemple : notification mobile

```yaml
alias: Fuji - Notification pipi/caca
description: Notifie quand Fuji a fait ses besoins à la litière
trigger:
  - trigger: event
    event_type: fuji_visit_completed
condition: []
action:
  - action: notify.mobile_app_ton_telephone
    data:
      title: "🐈 Fuji"
      message: >-
        {% set emoji = {'pipi': '💧', 'caca': '💩'} %}
        {{ emoji.get(trigger.event.data.type, '🐾') }}
        Fuji a fait {{ trigger.event.data.type }}
        ({{ trigger.event.data.duration_seconds }} s)
mode: queued
```

### Variante : notifier uniquement pour un caca

```yaml
alias: Fuji - Notification caca uniquement
trigger:
  - trigger: event
    event_type: fuji_visit_completed
condition:
  - condition: template
    value_template: "{{ trigger.event.data.type == 'caca' }}"
action:
  - action: notify.mobile_app_ton_telephone
    data:
      title: "💩 Fuji a fait caca"
      message: "Litière à nettoyer (durée {{ trigger.event.data.duration_seconds }} s)"
mode: single
```

> 💡 Si plusieurs litières/appareils Fuji sont configurés, filtre sur
> `trigger.event.data.device_id` (visible dans Outils de développement →
> Événements, ou dans Paramètres → Appareils → Fuji → ⋮ → Informations sur
> l'appareil) pour ne notifier que pour la bonne litière.

### Alternative : déclencheur sur l'état du capteur

Si tu préfères ne pas utiliser l'événement, un déclencheur d'état sur
`sensor...dernier_passage` fonctionne aussi (les valeurs sont alors
capitalisées : `Pipi` / `Caca`) :

```yaml
alias: Fuji - Notification (via capteur d'état)
trigger:
  - trigger: state
    entity_id: sensor.litiere_fuji_dernier_passage
    to:
      - "Pipi"
      - "Caca"
action:
  - action: notify.mobile_app_ton_telephone
    data:
      title: "🐈 Fuji"
      message: "Fuji a fait {{ trigger.to_state.state }}"
mode: single
```

## Carte Lovelace "Litière Fuji"

En plus de l'intégration `custom_components/fuji`, ce dépôt fournit une
carte Lovelace custom (`custom_components/fuji/frontend/fuji-litter-card.js`), dans le même esprit que
[sionetta/wm_animated_ha_card](https://github.com/sionetta/wm_animated_ha_card) :
une illustration en haut, un bandeau de statut, et un résumé des
derniers passages en bas.

**États de l'illustration :**
- Litière vide → pas de présence (`Absence`)
- Litière + chat → présence détectée (`Présence`)
- Litière + emoji 💧/💩 → affiché pendant `cooldown_minutes` (15 min par
  défaut) après la fin d'un passage concluant (`Pipi`/`Caca`), puis retour
  automatique à "Absence".

Sous l'illustration, un bandeau affiche l'état en texte (`Absence` /
`Présence` / `Pipi` / `Caca`) avec son emoji, et sous le bandeau, les
3 derniers passages concluants (durée + heure).

### Installation

1. Copie `custom_components/fuji/frontend/fuji-litter-card.js` dans `/config/www/` et le contenu de
   `custom_components/fuji/media/` dans `/config/www/fuji/media/`. Ces images
   sont servies par Home Assistant sous `/local/fuji/media/`.
2. Ajoute la ressource pour que Home Assistant charge le fichier :
   - **Tableau de bord en mode "Tableau de bord" (UI / storage, le mode
     par défaut)** : Paramètres → Tableaux de bord → menu ⋮ (en haut à
     droite) → **Ressources** → **Ajouter une ressource** →
     URL `/local/fuji-litter-card.js`, type **Module JavaScript**.
     ⚠️ Dans ce mode, le bloc `lovelace: resources:` en YAML est
     **ignoré** (Home Assistant log un avertissement
     "Lovelace is running in storage mode. Define resources via user
     interface") — c'est la cause la plus fréquente pour laquelle la
     carte n'apparaît pas dans la liste : il faut passer par l'UI.
   - **Tableau de bord entièrement en mode YAML**
     (`lovelace: mode: yaml` au niveau racine) : ajoute plutôt dans
     `configuration.yaml` :

     ```yaml
     lovelace:
       resources:
         - url: /local/fuji-litter-card.js
           type: module
     ```

   Dans les deux cas, un redémarrage (ou au moins un rechargement complet
   du cache navigateur, Ctrl+Maj+R) est nécessaire après l'ajout.
3. Ajoute la carte à un tableau de bord :
   - **Éditeur visuel** : clique sur "Ajouter une carte", cherche
     "Fuji Litter Card" dans la liste, puis sélectionne tes capteurs dans
     les champs proposés (présence, dernier passage, historique, durée en
     cours...). Chaque instance de la carte peut être configurée
     indépendamment, sans toucher au YAML.
   - **YAML** : voir
     [`examples/fuji_litter_card_example.yaml`](examples/fuji_litter_card_example.yaml).

> Si la carte reste absente de la liste après avoir ajouté la ressource :
> vérifie que le fichier est bien accessible (`http://TON_HA/local/fuji-litter-card.js`
> doit répondre 200), puis vide le cache du navigateur — les modules JS
> sont agressivement mis en cache par le navigateur.
>
> 💡 Après **chaque mise à jour** de `custom_components/fuji/frontend/fuji-litter-card.js` (par exemple en
> changeant les illustrations), le navigateur peut continuer à servir
> l'ancienne version depuis son cache même après un Ctrl+Maj+R. Le plus
> fiable est d'ajouter/incrémenter un paramètre de version sur l'URL de la
> ressource, par ex. `/local/fuji-litter-card.js?v=2`, dans
> Paramètres → Tableaux de bord → ⋮ → Ressources (modifier la ressource
> existante plutôt que d'en recréer une).


### Configuration

| Option | Requis | Défaut | Description |
|---|---|---|---|
| `presence_entity` | **oui** | — | `binary_sensor` de présence de l'intégration Fuji. |
| `last_visit_entity` | **oui** | — | `sensor` "Dernier passage" (état `Pipi`/`Caca`/`Aucun`). |
| `history_entity` | non | — | `sensor` "Historique des passages" (attribut `visits`), pour le bloc des 3 derniers passages. |
| `current_duration_entity` | non | — | `sensor` "Durée de la visite en cours", pour un chrono live pendant une présence. |
| `name` | non | `Litière` | Titre de la carte. |
| `cooldown_minutes` | non | `15` | Durée d'affichage de l'emoji pipi/caca après un passage avant retour à "Absence". `0` = ne jamais revenir automatiquement. |
| `history_count` | non | `3` | Nombre de passages affichés dans le bloc historique. |

import type { ActionType, Category, Channel, Priority, Request, Sentiment } from './types'

// ── Métadonnées d'affichage (libellés + couleurs des badges) ────────────────
export const CATEGORY_META: Record<Category, { label: string; color: string }> = {
  livraison: { label: 'Livraison', color: '#7c5cff' },
  abonnement: { label: 'Abonnement', color: '#9a82ff' },
  facturation: { label: 'Facturation', color: '#34d399' },
  produit: { label: 'Produit / éditorial', color: '#60a5fa' },
  reclamation: { label: 'Réclamation', color: '#fb7185' },
}

export const PRIORITY_META: Record<Priority, { label: string; color: string }> = {
  haute: { label: 'Haute', color: '#fb7185' },
  moyenne: { label: 'Moyenne', color: '#fbbf24' },
  basse: { label: 'Basse', color: '#94a3b8' },
}

export const SENTIMENT_META: Record<Sentiment, { label: string; color: string }> = {
  neutre: { label: 'Neutre', color: '#94a3b8' },
  mecontent: { label: 'Mécontent', color: '#fb923c' },
  urgent: { label: 'Urgent', color: '#fb7185' },
}

export const CHANNEL_META: Record<Channel, { label: string }> = {
  email: { label: 'Email' },
  form: { label: 'Formulaire web' },
  phone: { label: 'Téléphone' },
  instagram: { label: 'Instagram' },
  facebook: { label: 'Facebook' },
  courrier: { label: 'Courrier' },
}

/** Libellé + couleur par issue (action prise par l'IA). */
export const ACTION_META: Record<ActionType, { label: string; short: string; color: string }> = {
  auto: { label: 'Réponse automatique envoyée', short: 'Auto-envoyée', color: '#34d399' },
  draft: { label: 'Brouillon prêt — à valider', short: 'Brouillon', color: '#7c5cff' },
  escalate: { label: 'Escaladé à un agent humain', short: 'Escaladé', color: '#fbbf24' },
}

// ── Les demandes entrantes (ordre = ordre d'arrivée dans la simulation) ──────
export const REQUESTS: Request[] = [
  {
    id: 'r1',
    channel: 'email',
    sender: 'Sylvie Marchand',
    senderRole: 'Parent abonné',
    message:
      "Bonjour, mon fils Hugo n'a pas reçu le numéro de juin de Mickey Junior. Pouvez-vous vérifier ce qu'il se passe ? Merci.",
    magazine: 'Mickey Junior',
    subscriberId: 'MJ-204871',
    receivedAt: '10:41',
    history: [
      { label: 'Abonné depuis', detail: 'mars 2022' },
      { label: 'Demandes précédentes', detail: '1 (changement d’adresse, 2023)' },
    ],
    analysis: {
      category: 'livraison',
      priority: 'moyenne',
      sentiment: 'neutre',
      confidence: 97,
      action: 'auto',
      reply:
        "Bonjour Sylvie, navré pour ce contretemps ! Je vois que le numéro de juin de Mickey Junior (abonnement MJ-204871) a bien été expédié. Je vous en renvoie un exemplaire dès aujourd'hui, sans frais — il devrait arriver sous 3 à 4 jours. Belle lecture à Hugo 🦆",
    },
  },
  {
    id: 'r2',
    channel: 'form',
    sender: 'Damien Roy',
    senderRole: 'Parent abonné',
    message: "Le dernier numéro de National Geographic Kids est arrivé tout déchiré, c'est dommage.",
    magazine: 'National Geographic Kids',
    subscriberId: 'NGK-118203',
    receivedAt: '10:43',
    analysis: {
      category: 'livraison',
      priority: 'basse',
      sentiment: 'mecontent',
      confidence: 95,
      action: 'auto',
      reply:
        "Bonjour Damien, désolé que ce numéro soit arrivé abîmé ! Un exemplaire neuf de National Geographic Kids part aujourd'hui, à nos frais. Merci de votre patience et bonne exploration aux enfants 🌍",
    },
  },
  {
    id: 'r3',
    channel: 'instagram',
    sender: '@mamie.de.jade',
    senderRole: 'Grand-mère',
    message: "Bonjour, l'abonnement Abricot de ma petite-fille Jade n'arrive plus depuis deux mois 😔",
    magazine: 'Abricot',
    subscriberId: 'ABR-067540',
    receivedAt: '10:44',
    analysis: {
      category: 'livraison',
      priority: 'haute',
      sentiment: 'mecontent',
      confidence: 92,
      action: 'draft',
      reply:
        "Bonjour, et merci de nous prévenir ! Je vois un souci d'acheminement sur l'abonnement Abricot de Jade (ABR-067540). Je relance la livraison et vous renvoie les 2 numéros manquants sans frais. Tout devrait rentrer dans l'ordre dès le prochain envoi 🍑",
    },
  },
  {
    id: 'r4',
    channel: 'phone',
    sender: 'Robert Lemaire',
    senderRole: 'Grand-père de Léo (tiers payeur)',
    message:
      "Appel transcrit — « Bonjour, j'offre l'abonnement Le Journal de Mickey à mon petit-fils Léo. Il déménage, je voudrais changer l'adresse de livraison. »",
    magazine: 'Le Journal de Mickey',
    subscriberId: 'JDM-339017',
    receivedAt: '10:46',
    threadId: 'thr-leo',
    history: [
      { label: 'Rôle', detail: 'Acheteur (abonnement cadeau)' },
      { label: 'Bénéficiaire', detail: 'Léo, 9 ans' },
    ],
    analysis: {
      category: 'abonnement',
      priority: 'moyenne',
      sentiment: 'neutre',
      confidence: 94,
      action: 'auto',
      reply:
        "Bonjour M. Lemaire, c'est noté pour l'abonnement Le Journal de Mickey de Léo (JDM-339017). Pouvez-vous me confirmer la nouvelle adresse ? Je la mets à jour immédiatement pour que le prochain numéro arrive au bon endroit. Merci pour ce joli cadeau 🎁",
    },
  },
  {
    id: 'r5',
    channel: 'email',
    sender: 'Sophie Lemaire',
    senderRole: 'Maman de Léo',
    message:
      "Bonjour, mon père a appelé pour l'abonnement de Léo au Journal de Mickey. Je vous confirme la nouvelle adresse : 14 rue des Lilas, 69003 Lyon. Merci !",
    magazine: 'Le Journal de Mickey',
    subscriberId: 'JDM-339017',
    receivedAt: '10:47',
    threadId: 'thr-leo',
    history: [
      { label: 'Conversation', detail: 'Reliée à l’appel de Robert Lemaire (grand-père)' },
      { label: 'Abonnement', detail: 'JDM-339017 · cadeau' },
    ],
    analysis: {
      category: 'abonnement',
      priority: 'moyenne',
      sentiment: 'neutre',
      confidence: 96,
      action: 'auto',
      reply:
        "Bonjour Sophie, parfait, merci ! Je relie votre message à l'appel de votre père concernant l'abonnement de Léo (JDM-339017). La nouvelle adresse — 14 rue des Lilas, 69003 Lyon — est enregistrée. Le prochain Journal de Mickey y sera livré. Belle journée à toute la famille !",
    },
  },
  {
    id: 'r6',
    channel: 'email',
    sender: 'Nadia Berthier',
    senderRole: 'Parent abonné',
    message: "J'ai été débitée deux fois ce mois-ci pour l'abonnement Picsou Magazine. Pouvez-vous régulariser ?",
    magazine: 'Picsou Magazine',
    subscriberId: 'PIC-512330',
    receivedAt: '10:49',
    analysis: {
      category: 'facturation',
      priority: 'haute',
      sentiment: 'mecontent',
      confidence: 96,
      action: 'draft',
      reply:
        "Bonjour Nadia, je confirme un double prélèvement sur l'abonnement Picsou Magazine (PIC-512330). Le remboursement du montant en trop est lancé — vous le verrez sous 3 à 5 jours ouvrés sur votre compte. Toutes nos excuses pour la gêne 🙏",
    },
  },
  {
    id: 'r7',
    channel: 'email',
    sender: 'Service RH — Groupe Vinet',
    senderRole: "Comité d'entreprise",
    message:
      "Bonjour, nous souhaitons une facture acquittée pour les 25 abonnements Epsiloon souscrits via notre CE. Pouvez-vous nous l'envoyer ?",
    magazine: 'Epsiloon',
    subscriberId: 'CE-EPS-0042',
    receivedAt: '10:51',
    analysis: {
      category: 'facturation',
      priority: 'moyenne',
      sentiment: 'neutre',
      confidence: 93,
      action: 'auto',
      reply:
        "Bonjour, avec plaisir ! Je génère la facture acquittée des 25 abonnements Epsiloon (réf. CE-EPS-0042) et vous l'envoie en PDF dans la foulée. N'hésitez pas si vous souhaitez un format particulier pour votre comptabilité.",
    },
  },
  {
    id: 'r8',
    channel: 'instagram',
    sender: '@papa.de.malo',
    senderRole: 'Parent',
    message: "À partir de quel âge conseillez-vous Tout Comprendre Junior ? Mon fils a 7 ans.",
    magazine: 'Tout Comprendre Junior',
    receivedAt: '10:52',
    analysis: {
      category: 'produit',
      priority: 'basse',
      sentiment: 'neutre',
      confidence: 98,
      action: 'auto',
      reply:
        "Bonjour ! Tout Comprendre Junior est pensé pour les 7-12 ans : votre fils de 7 ans est pile dans la cible 👍 Les sujets sont expliqués simplement, avec beaucoup d'images. Je peux vous envoyer un numéro découverte si vous le souhaitez !",
    },
  },
  {
    id: 'r9',
    channel: 'facebook',
    sender: 'Christine Faure',
    senderRole: 'Parent abonné',
    message: "Pourquoi le format de Pirouette a-t-il changé ? Mon petit était habitué à l'ancien.",
    magazine: 'Pirouette',
    subscriberId: 'PIR-088114',
    receivedAt: '10:54',
    analysis: {
      category: 'produit',
      priority: 'basse',
      sentiment: 'mecontent',
      confidence: 90,
      action: 'auto',
      reply:
        "Bonjour Christine, merci pour votre retour ! Le format de Pirouette a évolué pour un papier plus épais et des pages détachables (les enfants adorent les activités à découper). Le contenu et l'esprit restent les mêmes. J'espère que votre petit s'y fera vite 🎨",
    },
  },
  {
    id: 'r10',
    channel: 'email',
    sender: 'Karim Haddad',
    senderRole: 'Parent',
    message: "Le code d'activation de l'appli Pili Pop reçu avec l'abonnement ne fonctionne pas.",
    magazine: 'Pili Pop',
    subscriberId: 'PIP-771200',
    receivedAt: '10:55',
    analysis: {
      category: 'produit',
      priority: 'moyenne',
      sentiment: 'neutre',
      confidence: 94,
      action: 'auto',
      reply:
        "Bonjour Karim, désolé pour ce souci de code Pili Pop ! L'ancien code avait expiré. En voici un nouveau, valable 12 mois : PILI-7X4K-2024. Il suffit de le saisir dans l'appli, rubrique « Activer ». Bon apprentissage des langues à votre enfant 🗣️",
    },
  },
  {
    id: 'r11',
    channel: 'form',
    sender: 'Élodie Petit',
    senderRole: 'Parent',
    message: "Le livre Quelle Histoire « Léonard de Vinci » commandé est arrivé avec des pages collées.",
    magazine: 'Quelle Histoire',
    subscriberId: 'QH-440918',
    receivedAt: '10:57',
    analysis: {
      category: 'produit',
      priority: 'basse',
      sentiment: 'mecontent',
      confidence: 93,
      action: 'draft',
      reply:
        "Bonjour Élodie, navré pour ce défaut sur le livre Quelle Histoire « Léonard de Vinci » ! Un exemplaire neuf part aujourd'hui, sans frais, et vous pouvez garder l'autre. Merci de votre compréhension 📚",
    },
  },
  {
    id: 'r12',
    channel: 'email',
    sender: 'Patrick Noël',
    senderRole: 'Grand-père (tiers payeur)',
    message: "Mon abonnement cadeau Sorcières pour ma petite-fille arrive à échéance. Comment le renouveler ?",
    magazine: 'Sorcières',
    subscriberId: 'SOR-156722',
    receivedAt: '10:58',
    analysis: {
      category: 'abonnement',
      priority: 'basse',
      sentiment: 'neutre',
      confidence: 95,
      action: 'auto',
      reply:
        "Bonjour M. Noël, quel beau cadeau à renouveler ! L'abonnement Sorcières (SOR-156722) peut être reconduit en un clic ici : [lien]. Vous pouvez aussi le passer en renouvellement automatique pour ne plus y penser. Je reste à votre disposition 🔮",
    },
  },
  {
    id: 'r13',
    channel: 'instagram',
    sender: '@famille.durand',
    senderRole: 'Parent',
    message: "Le podcast lié au Monde des ados ne se lance plus depuis la mise à jour. C'est en panne ?",
    magazine: 'Le Monde des ados',
    receivedAt: '11:00',
    analysis: {
      category: 'produit',
      priority: 'moyenne',
      sentiment: 'neutre',
      confidence: 88,
      action: 'auto',
      reply:
        "Bonjour ! Merci du signalement. Un correctif du lecteur podcast du Monde des ados est en cours de déploiement — il sera réglé d'ici demain. En attendant, l'écoute fonctionne sur la version web : [lien]. Désolé pour la gêne 🎧",
    },
  },
  {
    id: 'r14',
    channel: 'email',
    sender: 'Valérie Dubois',
    senderRole: 'Parent abonné',
    message:
      "C'est la troisième fois que je signale un problème de livraison sur l'abonnement de ma fille et personne ne fait rien. Si ça continue je résilie tout et je préviens autour de moi. C'est inadmissible.",
    magazine: 'Abricot',
    subscriberId: 'ABR-203559',
    receivedAt: '11:02',
    history: [
      { label: 'Abonnée depuis', detail: 'janvier 2021' },
      { label: 'Réclamations', detail: '3 sur 2 mois (livraison)' },
    ],
    analysis: {
      category: 'reclamation',
      priority: 'haute',
      sentiment: 'urgent',
      confidence: 97,
      action: 'escalate',
      escalationTo: 'Léa — Pôle relation abonnés',
      escalationReason:
        "Cliente fidèle (2021), 3e réclamation non résolue, menace de résiliation et bouche-à-oreille négatif. Un geste commercial et un contact humain sont nécessaires — l'IA ne traite pas seule.",
    },
  },
  {
    id: 'r15',
    channel: 'phone',
    sender: 'Jean-Marc Olivier',
    senderRole: 'Parent abonné',
    message:
      "Appel transcrit — « J'ai eu trois numéros abîmés d'affilée pour Picsou, et le SAV m'a baladé. Je veux un geste commercial ou j'arrête. »",
    magazine: 'Picsou Magazine',
    subscriberId: 'PIC-330142',
    receivedAt: '11:04',
    analysis: {
      category: 'reclamation',
      priority: 'haute',
      sentiment: 'mecontent',
      confidence: 95,
      action: 'escalate',
      escalationTo: 'Thomas — Pôle commercial & gestes',
      escalationReason:
        "Demande explicite de geste commercial après plusieurs incidents. Décision tarifaire à valider par un humain — routé vers le pôle commercial avec tout l'historique.",
    },
  },
  {
    id: 'r16',
    channel: 'email',
    sender: 'Aurélie Mercier',
    senderRole: 'Parent',
    message: "Je souhaite résilier l'abonnement Mickey Junior de mon fils, il a un peu grandi. Comment procéder ?",
    magazine: 'Mickey Junior',
    subscriberId: 'MJ-198044',
    receivedAt: '11:05',
    analysis: {
      category: 'abonnement',
      priority: 'moyenne',
      sentiment: 'neutre',
      confidence: 96,
      action: 'draft',
      reply:
        "Bonjour Aurélie, bien sûr, je m'en occupe. La résiliation de Mickey Junior (MJ-198044) prendra effet à la fin de la période en cours, sans frais. Si votre fils grandit, peut-être aimerait-il Le Journal de Mickey (dès 8 ans) ? Je peux vous proposer un mois découverte — sans engagement. Belle journée !",
    },
  },
  {
    id: 'r17',
    channel: 'email',
    sender: 'Hélène Faivre',
    senderRole: 'Parent abonné',
    message:
      "Je suis choquée par le ton d'un article du dernier Le Monde des ados, je ne le trouve pas adapté à des adolescents. Je veux une explication de la rédaction, sinon je résilie et j'en parle autour de moi.",
    magazine: 'Le Monde des ados',
    subscriberId: 'MDA-077413',
    receivedAt: '11:07',
    analysis: {
      category: 'reclamation',
      priority: 'haute',
      sentiment: 'mecontent',
      confidence: 96,
      action: 'escalate',
      escalationTo: 'Camille — Rédaction en chef',
      escalationReason:
        "Contestation éditoriale sensible avec menace publique. Relève d'une réponse de la rédaction, pas du SAV — routé vers la rédactrice en chef avec le contexte.",
    },
  },
]

/**
 * Ordre d'arrivée dans la simulation — volontairement entrelacé pour montrer la
 * variété (auto / brouillon / escalade) ET l'omnicanal dès les premières cartes.
 */
const _byId = Object.fromEntries(REQUESTS.map((r) => [r.id, r]))
export const SIM_SEQUENCE: Request[] = [
  'r1', // auto
  'r4', // auto · omnicanal (appel grand-père)
  'r5', // auto · omnicanal (email parent) → fusion visible tout de suite
  'r14', // escalade (dès la 4e carte)
  'r6', // brouillon
  'r8', // auto
  'r17', // escalade · rédaction
  'r3', // brouillon
  'r2', // auto
  'r15', // escalade · commercial
  'r16', // brouillon
  'r9', // auto
  'r10', // auto
  'r11', // brouillon
  'r7', // auto
  'r12', // auto
  'r13', // auto
].map((id) => _byId[id])


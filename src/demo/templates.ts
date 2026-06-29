import type { Category } from './types'

/** Bibliothèque de modèles de réponse — dans le ton chaleureux UHM, proches des familles. */
export const TEMPLATES: {
  id: string
  category: Category
  title: string
  trigger: string
  body: string
  uses: number
}[] = [
  {
    id: 't1',
    category: 'livraison',
    title: 'Numéro non reçu',
    trigger: '« je n’ai pas reçu le numéro… »',
    body: "Bonjour [Prénom], navré pour ce contretemps ! Je vois que le dernier numéro de [Magazine] (abonnement [N°]) a bien été expédié. Je vous en renvoie un exemplaire dès aujourd’hui, sans frais — il devrait arriver sous 3 à 4 jours. Belle lecture à [Enfant] !",
    uses: 184,
  },
  {
    id: 't2',
    category: 'livraison',
    title: 'Magazine abîmé',
    trigger: '« arrivé déchiré / abîmé »',
    body: "Bonjour [Prénom], désolé que ce numéro soit arrivé abîmé ! Un exemplaire neuf de [Magazine] part aujourd’hui, à nos frais. Vous pouvez garder l’autre. Merci de votre patience 🌟",
    uses: 96,
  },
  {
    id: 't3',
    category: 'abonnement',
    title: 'Changement d’adresse',
    trigger: '« déménagement / nouvelle adresse »',
    body: "Bonjour [Prénom], c’est noté pour l’abonnement [Magazine] ([N°]). La nouvelle adresse est enregistrée : le prochain numéro y sera livré. Merci de nous avoir prévenus !",
    uses: 142,
  },
  {
    id: 't4',
    category: 'facturation',
    title: 'Double prélèvement',
    trigger: '« débité deux fois »',
    body: "Bonjour [Prénom], je confirme un double prélèvement sur l’abonnement [Magazine] ([N°]). Le remboursement du montant en trop est lancé — vous le verrez sous 3 à 5 jours ouvrés. Toutes nos excuses pour la gêne 🙏",
    uses: 58,
  },
  {
    id: 't5',
    category: 'produit',
    title: 'Âge conseillé',
    trigger: '« à partir de quel âge ? »',
    body: "Bonjour [Prénom] ! [Magazine] est pensé pour les [tranche d’âge] : votre enfant est pile dans la cible 👍 Les sujets sont expliqués simplement, avec beaucoup d’images. Je peux vous envoyer un numéro découverte si vous le souhaitez !",
    uses: 73,
  },
  {
    id: 't6',
    category: 'produit',
    title: 'Code d’activation appli',
    trigger: '« le code ne fonctionne pas »',
    body: "Bonjour [Prénom], désolé pour ce souci de code ! L’ancien avait expiré. En voici un nouveau, valable 12 mois : [CODE]. Il suffit de le saisir dans l’appli, rubrique « Activer ». Bon usage à [Enfant] !",
    uses: 41,
  },
  {
    id: 't7',
    category: 'abonnement',
    title: 'Renouvellement cadeau',
    trigger: '« renouveler l’abonnement offert »',
    body: "Bonjour [Prénom], quel beau cadeau à renouveler ! L’abonnement [Magazine] ([N°]) se reconduit en un clic ici : [lien]. Vous pouvez aussi activer le renouvellement automatique pour ne plus y penser 🎁",
    uses: 67,
  },
  {
    id: 't8',
    category: 'abonnement',
    title: 'Résiliation',
    trigger: '« je souhaite résilier »',
    body: "Bonjour [Prénom], bien sûr, je m’en occupe. La résiliation de [Magazine] ([N°]) prendra effet à la fin de la période en cours, sans frais. Si votre enfant grandit, peut-être aimerait-il [Magazine suggéré] ? Je peux vous proposer un mois découverte, sans engagement.",
    uses: 39,
  },
]

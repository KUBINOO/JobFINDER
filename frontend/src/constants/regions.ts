export interface Region {
  id: string
  name: string
  city: string
  icon: string
  tag?: string
}

export const CZECH_REGIONS: Region[] = [
  { id: "praha", name: "Hlavní město Praha", city: "Praha", icon: "🏛️", tag: "Nejvíce nabídek" },
  { id: "stredocesky", name: "Středočeský kraj", city: "Praha (sídlo kraje)", icon: "🌲", tag: "Okolí Prahy" },
  { id: "jihomoravsky", name: "Jihomoravský kraj", city: "Brno", icon: "🍷", tag: "IT & Tech hub" },
  { id: "moravskoslezsky", name: "Moravskoslezský kraj", city: "Ostrava", icon: "⚙️", tag: "Průmysl & IT" },
  { id: "plzensky", name: "Plzeňský kraj", city: "Plzeň", icon: "🍺" },
  { id: "jihocesky", name: "Jihočeský kraj", city: "České Budějovice", icon: "🏰" },
  { id: "olomoucky", name: "Olomoucký kraj", city: "Olomouc", icon: "🎓" },
  { id: "kralovehradecky", name: "Královéhradecký kraj", city: "Hradec Králové", icon: "🌾" },
  { id: "pardubicky", name: "Pardubický kraj", city: "Pardubice", icon: "🐎" },
  { id: "zlinsky", name: "Zlínský kraj", city: "Zlín", icon: "👞" },
  { id: "ustecky", name: "Ústecký kraj", city: "Ústí nad Labem", icon: "⛰️" },
  { id: "liberecky", name: "Liberecký kraj", city: "Liberec", icon: "🏔️" },
  { id: "vysocina", name: "Kraj Vysočina", city: "Jihlava", icon: "🌲" },
  { id: "karlovarsky", name: "Karlovarský kraj", city: "Karlovy Vary", icon: "♨️" },
]

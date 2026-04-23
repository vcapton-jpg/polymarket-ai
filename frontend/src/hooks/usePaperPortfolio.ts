import { useQuery } from "@tanstack/react-query"
import { fetchPaperPositions } from "@/lib/api/paper"

export function usePaperPortfolio() {
  return useQuery({
    queryKey: ["paper-positions"],
    queryFn: fetchPaperPositions,
    staleTime: 15_000,
  })
}

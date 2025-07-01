import { ThemeProvider } from "@/components/ThemeProvider"
import { Toaster } from "sonner"
import { cn } from "@/lib/utils"

interface RootLayoutProps {
  children: React.ReactNode
  className?: string
}

export function RootLayout({ children, className }: RootLayoutProps) {
  return (
    <ThemeProvider defaultTheme={{ base: "system", color: "default" }}>
      <div className={cn("min-h-screen bg-background font-sans antialiased", className)}>
        {children}
        <Toaster />
      </div>
    </ThemeProvider>
  )
}
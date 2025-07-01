import { createContext, useContext, useEffect, useState, type ReactNode } from "react"
import { allThemes, getTheme, type Theme } from "@/lib/themes"

// Define theme settings
type BaseTheme = "dark" | "light" | "system"
type ColorTheme = "default" | "blue" | "green" | "purple" | "red"

type ThemeSettings = {
  base: BaseTheme
  color: ColorTheme
}

type ThemeProviderState = {
  theme: ThemeSettings
  setTheme: (theme: Partial<ThemeSettings>) => void
  setBaseTheme: (base: BaseTheme) => void
  setColorTheme: (color: ColorTheme) => void
  getThemeValue: (variable: string) => string
  availableThemes: ColorTheme[]
}

interface ThemeProviderProps {
  children: ReactNode
  defaultTheme?: Partial<ThemeSettings>
}

// Create context with default values
const ThemeProviderContext = createContext<ThemeProviderState>({
  theme: { base: "system", color: "default" },
  setTheme: () => null,
  setBaseTheme: () => null,
  setColorTheme: () => null,
  getThemeValue: () => "",
  availableThemes: ["default", "blue", "green", "purple", "red"],
})

// Hook for components to access theme context
export const useTheme = () => {
  const context = useContext(ThemeProviderContext)
  
  if (context === undefined)
    throw new Error("useTheme must be used within a ThemeProvider")
    
  return context
}

// Apply theme CSS variables to the document
function applyTheme(settings: ThemeSettings): void {
  const root = window.document.documentElement
  const theme = getTheme(settings.color)
  const mode = getEffectiveMode(settings.base)
  const cssVars = theme.cssVars[mode]
  if (!cssVars) return;

  Object.entries(cssVars).forEach(([key, value]) => {
    // Check if the key is a color variable (has HSL values) or a non-color variable
    if (key.includes("--radius") || value.includes("rem") || value.includes("px")) {
      root.style.setProperty(key, value)
    } else {
      root.style.setProperty(key, `hsl(${value})`)
    }
  })

  // Update class for mode
  root.classList.remove("light", "dark")
  root.classList.add(mode)
}

// Get effective color mode (resolving system preference)
function getEffectiveMode(baseTheme: BaseTheme): "light" | "dark" {
  if (baseTheme === "system") {
    return window.matchMedia("(prefers-color-scheme: dark)").matches
      ? "dark"
      : "light"
  }
  return baseTheme
}

export function ThemeProvider({ 
  children, 
  defaultTheme = { base: "system", color: "default" }
}: ThemeProviderProps) {
  // Initialize theme state from localStorage or defaults
  const [settings, setThemeSettings] = useState<ThemeSettings>(() => {
    const savedTheme = localStorage.getItem("theme-settings")
    if (savedTheme) {
      try {
        return JSON.parse(savedTheme) as ThemeSettings
      } catch (e) {
        // If parsing fails, use defaults
      }
    }
    
    return {
      base: defaultTheme.base || "system",
      color: defaultTheme.color || "default"
    }
  })

  // Apply theme when settings change
  useEffect(() => {
    applyTheme(settings)
    localStorage.setItem("theme-settings", JSON.stringify(settings))
  }, [settings])

  // Media query listener for system theme changes
  useEffect(() => {
    if (settings.base !== "system") return
    
    const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)")
    
    const handleChange = () => {
      applyTheme(settings)
    }
    
    mediaQuery.addEventListener("change", handleChange)
    return () => mediaQuery.removeEventListener("change", handleChange)
  }, [settings])

  // Get the current theme object
  const currentTheme = getTheme(settings.color)
  const currentMode = getEffectiveMode(settings.base)

  // Helper to get a specific CSS variable value from the current theme
  const getThemeValue = (variable: string): string => {
    return currentTheme.cssVars[currentMode][variable] || ""
  }

  // Theme setters
  const setTheme = (newSettings: Partial<ThemeSettings>) => {
    console.log('setTheme called with:', newSettings)
    setThemeSettings(prev => ({
      ...prev,
      ...newSettings
    }))
  }

  const setBaseTheme = (base: BaseTheme) => {
    console.log('setBaseTheme called with:', base)
    setThemeSettings(prev => ({
      ...prev,
      base
    }))
  }

  const setColorTheme = (color: ColorTheme) => {
    setThemeSettings(prev => ({
      ...prev,
      color
    }))
  }

  // Available theme colors
  const availableThemes = allThemes.map(theme => theme.name) as ColorTheme[]

  const value = {
    theme: settings,
    setTheme,
    setBaseTheme,
    setColorTheme,
    getThemeValue,
    availableThemes
  }

  return (
    <ThemeProviderContext.Provider value={value}>
      {children}
    </ThemeProviderContext.Provider>
  )
}

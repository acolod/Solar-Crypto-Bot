import { useEffect, useRef } from 'react';
import html2canvas from 'html2canvas-pro';

interface ScreenshotComponentProps {
  selector?: string; // Optional selector to specify what element to screenshot
  children: React.ReactNode;
}

/**
 * Component that listens for "take-screenshot" messages from the parent iframe
 * and responds with the screenshot data.
 */
const ScreenshotComponent: React.FC<ScreenshotComponentProps> = ({ 
  selector = 'body', 
  children 
}) => {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleMessage = async (event: MessageEvent) => {
      // Verify the origin matches our expected frontend URL
      if (event.origin !== 'https://solarapp.dev') {
        return;
      }

      // Check if this is a screenshot request
      if (event.data === 'take-screenshot') {
        try {
          // Determine what to capture - always use document.documentElement for full viewport
          const targetElement = document.documentElement;
          
          // Force the container to be at least the full viewport height
          document.body.style.minHeight = '100vh';
          document.documentElement.style.minHeight = '100vh';
          
          // Give the browser a moment to apply the style changes
          await new Promise(resolve => setTimeout(resolve, 50));
          
          // Take the screenshot with viewport dimensions
          const canvas = await html2canvas(targetElement, {
            width: window.innerWidth,
            height: window.innerHeight,
            windowWidth: window.innerWidth,
            windowHeight: window.innerHeight,
            scrollX: 0,
            scrollY: 0,
            scale: 2, // Higher resolution
            useCORS: true,
            allowTaint: true,
            backgroundColor: null,
            logging: false,
            foreignObjectRendering: true
          });
          
          // Convert to blob
          const blob = await new Promise<Blob>((resolve) => {
            canvas.toBlob((blob) => {
              if (blob) resolve(blob);
              else resolve(new Blob([])); // Fallback empty blob
            }, 'image/png', 1.0); // Use highest quality
          });
          
          // Convert to base64
          const reader = new FileReader();
          reader.readAsDataURL(blob);
          reader.onloadend = () => {
            const base64data = reader.result;
            
            // Send the screenshot data back to the parent
            if (window.parent) {
              window.parent.postMessage({
                type: 'screenshot-data',
                data: base64data,
                dimensions: { 
                  width: window.innerWidth, 
                  height: window.innerHeight,
                  aspectRatio: window.innerWidth / window.innerHeight
                }
              }, 'https://solarapp.dev');
            }
          };
        } catch (error) {
          console.error('Error taking screenshot:', error);
          // Send error message back to parent
          if (window.parent) {
            window.parent.postMessage({
              type: 'screenshot-error',
              error: 'Failed to take screenshot'
            }, 'https://solarapp.dev');
          }
        }
      }
    };

    // Add event listener for messages
    window.addEventListener('message', handleMessage);

    // Clean up
    return () => {
      window.removeEventListener('message', handleMessage);
    };
  }, [selector]);

  return (
    <div ref={containerRef} style={{ width: '100%', height: '100%', overflow: 'visible' }}>
      {children}
    </div>
  );
};

export default ScreenshotComponent;

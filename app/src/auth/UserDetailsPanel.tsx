import React, { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

interface UserDetailsPanelProps {
    userDetails: Record<string, any>;
    onLogout: () => void;
}

export const UserDetailsPanel: React.FC<UserDetailsPanelProps> = ({ userDetails, onLogout }) => {
    const [isOpen, setIsOpen] = useState(false);
    const panelRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        const handleClickOutside = (event: MouseEvent) => {
            if (panelRef.current && !panelRef.current.contains(event.target as Node)) {
                setIsOpen(false);
            }
        };

        if (isOpen) {
            document.addEventListener('mousedown', handleClickOutside);
        }

        return () => {
            document.removeEventListener('mousedown', handleClickOutside);
        };
    }, [isOpen]);

    const formatValue = (value: any): string => {
        if (value === null || value === undefined) return '—';
        if (typeof value === 'object') return JSON.stringify(value);
        return String(value);
    };

    const formatKey = (key: string): string => {
        return key.charAt(0).toUpperCase() + key.slice(1).replace(/([A-Z])/g, ' $1');
    };

    return (
        <div className="fixed bottom-4 right-4 z-50" ref={panelRef}>
            <AnimatePresence>
                {isOpen && (
                    <motion.div
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: 10 }}
                        transition={{ duration: 0.2 }}
                        className="absolute bottom-12 right-0 w-64 bg-white rounded-lg shadow-lg overflow-hidden mb-2"
                    >
                        <div className="p-3 border-b border-gray-100">
                            <h3 className="text-sm font-medium text-gray-800">Account Information</h3>
                        </div>

                        <div className="max-h-64 overflow-y-auto">
                            {Object.entries(userDetails).map(([key, value]) => (
                                <div key={key} className="px-3 py-2 border-b border-gray-100 last:border-0">
                                    <div className="text-xs font-medium text-gray-500">{formatKey(key)}</div>
                                    <div className="text-sm text-gray-800 break-all mt-0.5">{formatValue(value)}</div>
                                </div>
                            ))}
                        </div>

                        <div className="p-3 bg-gray-50">
                            <button
                                onClick={onLogout}
                                className="w-full flex items-center justify-center px-3 py-1.5 bg-white border border-gray-200 text-gray-700 text-sm font-medium rounded-md hover:bg-gray-50 transition-colors focus:outline-none focus:ring-2 focus:ring-gray-200"
                            >
                                Sign out
                            </button>
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>

            <motion.button
                onClick={() => setIsOpen(!isOpen)}
                className="flex items-center justify-center w-10 h-10 rounded-full bg-white shadow-md focus:outline-none focus:ring-2 focus:ring-gray-200"
                whileTap={{ scale: 0.95 }}
            >
                <div className="w-7 h-7 rounded-full bg-gray-800 flex items-center justify-center text-white text-sm font-medium">
                    {userDetails.email?.charAt(0).toUpperCase() || '?'}
                </div>
            </motion.button>
        </div>
    );
};
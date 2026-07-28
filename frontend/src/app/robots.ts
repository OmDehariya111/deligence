import { MetadataRoute } from 'next';

export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: '*',
      allow: '/',
      disallow: ['/admin/', '/api/', '/job/', '/history/', '/settings/'],
    },
    sitemap: 'https://deligenx.ai/sitemap.xml',
  };
}

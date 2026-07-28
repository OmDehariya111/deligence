import { MetadataRoute } from 'next';

export default function sitemap(): MetadataRoute.Sitemap {
  return [
    {
      url: 'https://deligenx.ai',
      changeFrequency: 'weekly',
      priority: 1,
    },
    {
      url: 'https://deligenx.ai/pricing',
      changeFrequency: 'monthly',
      priority: 0.8,
    },
  ];
}

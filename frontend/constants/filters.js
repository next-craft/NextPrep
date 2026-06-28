// Listing filter keys — shared by the (server) listings page and the (client)
// ListingFilters / MobileFilters. Kept in a plain, non-'use client' module so Server
// Components receive the real array. (A `'use client'` module only exports client
// references across the RSC boundary, so importing this from a server component there
// yields a proxy, not the array — hence "FILTER_KEYS.forEach is not a function".)
export const FILTER_KEYS = ['q', 'exam_category', 'listing_type', 'condition', 'state', 'city', 'subject', 'college']

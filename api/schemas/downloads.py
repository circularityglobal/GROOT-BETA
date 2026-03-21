"""Pydantic schemas for product download registration and analytics."""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
import re


class DownloadRegisterRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    email: str = Field(..., min_length=3, max_length=254)
    product: str = Field(..., pattern=r"^(browser|pillars|wizardos|cluster)$")
    platform: Optional[str] = Field(None, pattern=r"^(windows|macos|linux|debian)$")
    eth_address: Optional[str] = Field(None, max_length=42)
    marketing_consent: bool = False
    referrer: Optional[str] = Field(None, max_length=2048)


class DownloadRegisterResponse(BaseModel):
    lead_id: str
    download_url: Optional[str] = None
    product: str
    message: str


class ProductInfo(BaseModel):
    name: str
    display_name: str
    tagline: str
    description: str
    repo: str
    available: bool
    version: Optional[str] = None
    downloads: Dict[str, str]


class ProductCatalogResponse(BaseModel):
    products: List[ProductInfo]


class DownloadStatsResponse(BaseModel):
    total_downloads: int
    total_waitlist: int
    by_product: Dict[str, int]
    by_platform: Dict[str, int]
    by_type: Dict[str, int]
    recent_leads: List[Dict[str, Any]]
    daily_counts: List[Dict[str, Any]]

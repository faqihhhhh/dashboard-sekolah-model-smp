from django.contrib import admin

from .models import AliasKabKota, AliasProvinsi, KabKota, Periode, Provinsi


class AliasProvinsiInline(admin.TabularInline):
    model = AliasProvinsi
    extra = 1


class AliasKabKotaInline(admin.TabularInline):
    model = AliasKabKota
    extra = 1


@admin.register(Provinsi)
class ProvinsiAdmin(admin.ModelAdmin):
    list_display = ("kode", "nama")
    search_fields = ("kode", "nama")
    inlines = [AliasProvinsiInline]


@admin.register(KabKota)
class KabKotaAdmin(admin.ModelAdmin):
    list_display = ("kode", "nama", "jenis", "provinsi")
    list_filter = ("jenis", "provinsi")
    search_fields = ("kode", "nama")
    inlines = [AliasKabKotaInline]


@admin.register(Periode)
class PeriodeAdmin(admin.ModelAdmin):
    list_display = ("nama", "jenis", "tanggal_mulai", "tanggal_selesai")
